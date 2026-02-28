from __future__ import annotations

import json
import os
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import requests

from .outbox import build_outbox_envelope
from .task_registry import TaskRegistry
from .telemetry import Telemetry


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskRecord:
    id: str
    task_type: str
    payload: Dict[str, Any]
    retries: int
    max_retries: int


class TaskEngine:
    """Durable task engine backed by Supabase REST."""

    def __init__(self, registry: TaskRegistry, telemetry: Optional[Telemetry] = None) -> None:
        self.registry = registry
        self.telemetry = telemetry
        self.supabase_url = os.environ.get("SUPABASE_URL", "")
        self.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self.supabase_url or not self.supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        self._host_id = f"{socket.gethostname()}:{os.getpid()}"
        self.max_retries = max(0, int(os.environ.get("OPENCLAW_STEP_MAX_RETRIES", "2")))
        self.backoff_ms = max(10, int(os.environ.get("OPENCLAW_STEP_BACKOFF_MS", "250")))

    def enqueue(self, task_type: str, payload: Dict[str, Any], schedule_for: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        item = dict(payload or {})
        item.setdefault("correlation_id", self._correlation_id())
        record = {
            "type": task_type,
            "payload_json": item,
            "status": TaskStatus.QUEUED.value,
            "scheduled_for": schedule_for or now,
            "retries": 0,
            "max_retries": item.get("max_retries", 5),
        }
        created = self._insert("tasks", record, return_representation=True)
        self._emit_outbox_event(
            mutation_key=f"tasks:{created.get('id', 'unknown')}:enqueue",
            aggregate_type="task",
            aggregate_id=str(created.get("id") or "unknown"),
            payload_delta={"status": TaskStatus.QUEUED.value, "type": task_type},
        )
        self._emit("task_enqueue", {"task_type": task_type, "task_id": created.get("id"), "correlation_id": item["correlation_id"]})
        return created

    def run_once(self, limit: int = 5) -> int:
        try:
            tasks = self._fetch_ready_tasks(limit=limit)
        except requests.RequestException as exc:
            self._emit("task_fetch_error", {"error": f"{type(exc).__name__}:{exc}"})
            return 0

        processed = 0
        for task in tasks:
            try:
                if self._is_duplicate(task):
                    self._mark_task(task["id"], TaskStatus.COMPLETED, {"duplicate": True})
                    continue
                record = self._lock_task(task)
                if not record:
                    continue
                processed += 1
                self._execute(record)
            except Exception as exc:  # noqa: BLE001
                self._emit(
                    "task_loop_error",
                    {"task_id": task.get("id"), "error": f"{type(exc).__name__}:{exc}"},
                )
                continue
        return processed

    def run_loop(self, interval_seconds: int = 10) -> None:
        while True:
            processed = self.run_once()
            self._emit("task_loop", {"processed": processed})
            time.sleep(interval_seconds)

    def _execute(self, task: TaskRecord) -> None:
        handler = self.registry.get(task.task_type)
        correlation_id = str((task.payload or {}).get("correlation_id") or self._correlation_id())
        if handler is None:
            self._mark_task(task.id, TaskStatus.FAILED, {"error": "handler_not_found", "correlation_id": correlation_id})
            return
        start = datetime.now(timezone.utc).isoformat()
        try:
            output = handler.handler(task.payload)
            end = datetime.now(timezone.utc).isoformat()
            self._insert(
                "task_runs",
                {
                    "task_id": task.id,
                    "status": TaskStatus.COMPLETED.value,
                    "started_at": start,
                    "ended_at": end,
                    "output_json": output,
                },
            )
            self._mark_task(task.id, TaskStatus.COMPLETED, {"result": "ok", "correlation_id": correlation_id})
        except Exception as exc:  # pylint: disable=broad-except
            end = datetime.now(timezone.utc).isoformat()
            try:
                self._insert(
                    "task_runs",
                    {
                        "task_id": task.id,
                        "status": TaskStatus.FAILED.value,
                        "started_at": start,
                        "ended_at": end,
                        "error": str(exc),
                    },
                )
            except requests.RequestException as write_exc:
                self._emit(
                    "task_run_write_error",
                    {
                        "task_id": task.id,
                        "correlation_id": correlation_id,
                        "error": f"{type(write_exc).__name__}:{write_exc}",
                    },
                )
            self._retry_or_fail(task, str(exc), correlation_id=correlation_id)

    def _fetch_ready_tasks(self, limit: int = 5) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        url = f"{self.supabase_url}/rest/v1/tasks"
        params = {
            "select": "id,type,payload_json,retries,max_retries,scheduled_for",
            "status": "eq.queued",
            "scheduled_for": f"lte.{now}",
            "order": "scheduled_for.asc",
            "limit": str(limit),
        }
        return self._get(url, params=params)

    def _lock_task(self, task: Dict[str, Any]) -> Optional[TaskRecord]:
        patch = {
            "status": TaskStatus.RUNNING.value,
            "locked_by": self._host_id,
            "locked_at": datetime.now(timezone.utc).isoformat(),
        }
        response = self._patch(
            f"tasks?id=eq.{task['id']}&status=eq.queued",
            patch,
            return_representation=True,
        )
        if not response:
            return None
        row = response[0]
        return TaskRecord(
            id=row["id"],
            task_type=row["type"],
            payload=row.get("payload_json", {}),
            retries=row.get("retries", 0),
            max_retries=row.get("max_retries", 5),
        )

    def _retry_or_fail(self, task: TaskRecord, error: str, *, correlation_id: str) -> None:
        retries = task.retries + 1
        if retries > task.max_retries:
            self._mark_task(
                task.id,
                TaskStatus.FAILED,
                {"error": error, "retries": retries, "correlation_id": correlation_id},
            )
            return
        backoff = min(3600, 2**retries * 10)
        scheduled_for = datetime.fromtimestamp(time.time() + backoff, tz=timezone.utc).isoformat()
        patch = {
            "status": TaskStatus.QUEUED.value,
            "retries": retries,
            "scheduled_for": scheduled_for,
            "locked_by": None,
            "locked_at": None,
        }
        try:
            self._patch(f"tasks?id=eq.{task.id}", patch)
        except requests.RequestException as exc:
            self._emit(
                "task_retry_update_error",
                {"task_id": task.id, "error": f"{type(exc).__name__}:{exc}", "correlation_id": correlation_id},
            )

    def _mark_task(self, task_id: str, status: TaskStatus, metadata: Dict[str, Any]) -> None:
        patch = {
            "status": status.value,
            "locked_by": None,
            "locked_at": None,
        }
        try:
            self._patch(f"tasks?id=eq.{task_id}", patch)
        except requests.RequestException as exc:
            self._emit(
                "task_mark_error",
                {"task_id": task_id, "status": status.value, "error": f"{type(exc).__name__}:{exc}"},
            )
        self._emit_outbox_event(
            mutation_key=f"tasks:{task_id}:status:{status.value}",
            aggregate_type="task",
            aggregate_id=str(task_id),
            payload_delta={"status": status.value},
        )
        self._emit("task_status", {"task_id": task_id, "status": status.value, **metadata})

    def _is_duplicate(self, task: Dict[str, Any]) -> bool:
        payload = task.get("payload_json") or {}
        key = payload.get("idempotency_key")
        if not key:
            return False
        url = f"{self.supabase_url}/rest/v1/tasks"
        params = {
            "select": "id",
            "payload_json->>idempotency_key": f"eq.{key}",
            "status": "in.(running,completed)",
        }
        existing = self._get(url, params=params)
        return len(existing) > 0

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        resp = self._request_with_retry("get", url, params=params)
        resp.raise_for_status()
        return resp.json()

    def _insert(self, table: str, record: Dict[str, Any], return_representation: bool = False) -> Dict[str, Any]:
        headers = self._headers()
        if return_representation:
            headers["Prefer"] = "return=representation"
        resp = self._request_with_retry(
            "post",
            f"{self.supabase_url}/rest/v1/{table}",
            headers=headers,
            data=json.dumps(record),
        )
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            return {}
        return data[0] if isinstance(data, list) and data else data

    def _patch(self, table_query: str, patch: Dict[str, Any], return_representation: bool = False) -> List[Dict[str, Any]]:
        headers = self._headers()
        if return_representation:
            headers["Prefer"] = "return=representation"
        resp = self._request_with_retry(
            "patch",
            f"{self.supabase_url}/rest/v1/{table_query}",
            headers=headers,
            data=json.dumps(patch),
        )
        resp.raise_for_status()
        return resp.json() if return_representation else []

    def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        timeout = kwargs.pop("timeout", 30)
        headers = kwargs.pop("headers", self._headers())
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                return requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    break
                backoff = min(15000, self.backoff_ms * (2**attempt))
                time.sleep(backoff / 1000.0)
        if isinstance(last_exc, Exception):
            raise last_exc
        raise RuntimeError("request failed without exception")

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }

    def _correlation_id(self) -> str:
        return f"task-{uuid.uuid4().hex[:12]}"

    def _emit(self, event: str, payload: Dict[str, Any]) -> None:
        if self.telemetry:
            self.telemetry.emit(event, payload)

    def _emit_outbox_event(
        self,
        *,
        mutation_key: str,
        aggregate_type: str,
        aggregate_id: str,
        payload_delta: Dict[str, Any],
    ) -> None:
        if os.environ.get("OPENCLAW_OUTBOX_EMIT", "1") == "0":
            return
        try:
            envelope = build_outbox_envelope(
                mutation_key=mutation_key,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload_delta=payload_delta,
                schema_version=1,
            )
            headers = self._headers()
            headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
            self._request_with_retry(
                "post",
                f"{self.supabase_url}/rest/v1/canonical_outbox",
                headers=headers,
                params={"on_conflict": "event_id"},
                data=json.dumps(envelope.as_record()),
                timeout=5,
            ).raise_for_status()
        except requests.RequestException as exc:
            self._emit(
                "outbox_write_error",
                {"mutation_key": mutation_key, "error": f"{type(exc).__name__}:{exc}"},
            )
