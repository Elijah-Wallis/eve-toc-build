from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import requests

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

    def enqueue(self, task_type: str, payload: Dict[str, Any], schedule_for: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "type": task_type,
            "payload_json": payload,
            "status": TaskStatus.QUEUED.value,
            "scheduled_for": schedule_for or now,
            "retries": 0,
            "max_retries": payload.get("max_retries", 5),
        }
        return self._insert("tasks", record, return_representation=True)

    def run_once(self, limit: int = 5) -> int:
        tasks = self._fetch_ready_tasks(limit=limit)
        processed = 0
        for task in tasks:
            if self._is_duplicate(task):
                self._mark_task(task["id"], TaskStatus.COMPLETED, {"duplicate": True})
                continue
            record = self._lock_task(task)
            if not record:
                continue
            processed += 1
            self._execute(record)
        return processed

    def run_loop(self, interval_seconds: int = 10) -> None:
        while True:
            processed = self.run_once()
            if self.telemetry:
                self.telemetry.emit("task_loop", {"processed": processed})
            time.sleep(interval_seconds)

    def _execute(self, task: TaskRecord) -> None:
        handler = self.registry.get(task.task_type)
        if handler is None:
            self._mark_task(task.id, TaskStatus.FAILED, {"error": "handler_not_found"})
            return
        start = datetime.now(timezone.utc).isoformat()
        try:
            output = handler.handler(task.payload)
            end = datetime.now(timezone.utc).isoformat()
            self._insert("task_runs", {
                "task_id": task.id,
                "status": TaskStatus.COMPLETED.value,
                "started_at": start,
                "ended_at": end,
                "output_json": output,
            })
            self._mark_task(task.id, TaskStatus.COMPLETED, {"result": "ok"})
        except Exception as exc:  # pylint: disable=broad-except
            end = datetime.now(timezone.utc).isoformat()
            self._insert("task_runs", {
                "task_id": task.id,
                "status": TaskStatus.FAILED.value,
                "started_at": start,
                "ended_at": end,
                "error": str(exc),
            })
            self._retry_or_fail(task, str(exc))

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

    def _retry_or_fail(self, task: TaskRecord, error: str) -> None:
        retries = task.retries + 1
        if retries > task.max_retries:
            self._mark_task(task.id, TaskStatus.FAILED, {"error": error, "retries": retries})
            return
        backoff = min(3600, 2 ** retries * 10)
        scheduled_for = datetime.fromtimestamp(time.time() + backoff, tz=timezone.utc).isoformat()
        patch = {
            "status": TaskStatus.QUEUED.value,
            "retries": retries,
            "scheduled_for": scheduled_for,
            "locked_by": None,
            "locked_at": None,
        }
        self._patch(f"tasks?id=eq.{task.id}", patch)

    def _mark_task(self, task_id: str, status: TaskStatus, metadata: Dict[str, Any]) -> None:
        patch = {
            "status": status.value,
            "locked_by": None,
            "locked_at": None,
        }
        self._patch(f"tasks?id=eq.{task_id}", patch)
        if self.telemetry:
            self.telemetry.emit("task_status", {"task_id": task_id, "status": status.value, **metadata})

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
        resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _insert(self, table: str, record: Dict[str, Any], return_representation: bool = False) -> Dict[str, Any]:
        headers = self._headers()
        if return_representation:
            headers["Prefer"] = "return=representation"
        resp = requests.post(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=headers,
            data=json.dumps(record),
            timeout=30,
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
        resp = requests.patch(
            f"{self.supabase_url}/rest/v1/{table_query}",
            headers=headers,
            data=json.dumps(patch),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json() if return_representation else []

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }
