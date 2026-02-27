from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from .task_engine import TaskEngine
from .telemetry import Telemetry


class CronScheduler:
    """Minimal cron scheduler backed by Supabase cron_jobs."""

    def __init__(self, engine: TaskEngine, telemetry: Optional[Telemetry] = None) -> None:
        self.engine = engine
        self.telemetry = telemetry
        self.supabase_url = os.environ.get("SUPABASE_URL", "")
        self.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self.supabase_url or not self.supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        self.max_retries = max(0, int(os.environ.get("OPENCLAW_STEP_MAX_RETRIES", "2")))
        self.backoff_ms = max(10, int(os.environ.get("OPENCLAW_STEP_BACKOFF_MS", "250")))

    def tick(self) -> int:
        now = datetime.now(timezone.utc)
        try:
            jobs = self._get_jobs()
        except requests.RequestException as exc:
            self._emit("cron_scheduler_error", {"error": f"{type(exc).__name__}:{exc}"})
            return 0

        fired = 0
        for job in jobs:
            try:
                cron = job.get("cron", "*")
                last_run = self._parse_ts(job.get("last_run_at"))
                next_run = self._parse_ts(job.get("next_run_at"))
                due, computed_next = self._is_due(cron, now, last_run, next_run)
                if not due:
                    continue
                payload = job.get("payload_json") or {}
                self.engine.enqueue(job.get("task_type"), payload)
                fired += 1
                self._update_job(job["id"], now, computed_next)
            except Exception as exc:  # noqa: BLE001
                self._emit(
                    "cron_job_error",
                    {"job_id": str(job.get("id")), "error": f"{type(exc).__name__}:{exc}"},
                )
                continue
        if fired:
            self._emit("cron_scheduler_fired", {"count": fired})
        return fired

    def _get_jobs(self) -> List[Dict[str, Any]]:
        url = f"{self.supabase_url}/rest/v1/cron_jobs"
        params = {
            "select": "id,name,cron,task_type,payload_json,last_run_at,next_run_at,active",
            "active": "eq.true",
        }
        return self._get(url, params=params)

    def _update_job(self, job_id: str, now: datetime, next_run: datetime) -> None:
        patch = {
            "last_run_at": now.isoformat(),
            "next_run_at": next_run.isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._patch(f"cron_jobs?id=eq.{job_id}", patch)

    def _is_due(
        self,
        cron: str,
        now: datetime,
        last_run: Optional[datetime],
        next_run: Optional[datetime],
    ) -> Tuple[bool, datetime]:
        if next_run and now < next_run:
            return False, next_run
        base = last_run or now
        computed_next = self._compute_next(cron, base)
        return now >= computed_next, computed_next

    def _compute_next(self, cron: str, base: datetime) -> datetime:
        fields = cron.strip().split()
        if len(fields) != 5:
            return base + timedelta(minutes=60)
        minute, hour, _, _, _ = fields

        def parse_field(value: str, max_value: int) -> List[int]:
            if value == "*":
                return list(range(0, max_value + 1))
            if value.startswith("*/"):
                step = int(value.split("/")[1])
                return list(range(0, max_value + 1, step))
            return [int(value)]

        minutes = parse_field(minute, 59)
        hours = parse_field(hour, 23)
        candidate = base.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(0, 1440):
            if candidate.minute in minutes and candidate.hour in hours:
                return candidate
            candidate += timedelta(minutes=1)
        return base + timedelta(minutes=60)

    def _parse_ts(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _get(self, url: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        resp = self._request_with_retry("get", url, params=params)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, table_query: str, patch: Dict[str, Any]) -> None:
        resp = self._request_with_retry(
            "patch",
            f"{self.supabase_url}/rest/v1/{table_query}",
            data=json.dumps(patch),
        )
        resp.raise_for_status()

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

    def _emit(self, event: str, payload: Dict[str, Any]) -> None:
        if self.telemetry:
            self.telemetry.emit(event, payload)
