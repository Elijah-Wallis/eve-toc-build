from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import os
import requests

from .context_store import ContextStore
from .registry_defaults import build_registry
from .task_engine import TaskEngine
from .telemetry import Telemetry


class TelegramRouter:
    """Routes Telegram commands into tasks and graph executions."""

    def __init__(self) -> None:
        self.registry = build_registry()
        self.telemetry = Telemetry("~/.openclaw-eve/runtime/telemetry.jsonl")
        self.engine = TaskEngine(self.registry, telemetry=self.telemetry)
        self.context = ContextStore()
        self.supabase_url = os.environ.get("SUPABASE_URL", "")
        self.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.n8n_api_base = os.environ.get("N8N_API_BASE", "https://elijah-wallis.app.n8n.cloud/api/v1")
        self.n8n_api_key = os.environ.get("N8N_API_KEY", "")

    def handle(self, text: str) -> Dict[str, Any]:
        parts = text.strip().split(" ", 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/runpack":
            workflow = arg.strip()
            if not workflow:
                return {"status": "error", "message": "workflow required"}
            cron = self._default_cron_for(workflow)
            job = self._upsert_cron_job(workflow, cron)
            record = self.engine.enqueue("n8n.trigger", {"workflow": workflow, "data": {}})
            status = "scheduled_with_warning" if isinstance(job, dict) and job.get("error") else "scheduled"
            return {"status": status, "cron": cron, "job": job, "task": record}

        if cmd == "/graph":
            graph = json.loads(arg) if arg else {}
            thread = self.context.create_thread("telegram")
            payload = {"graph": graph, "context": {}, "thread_name": "telegram"}
            self.context.append_event(thread["id"], "telegram_graph_request", payload)
            record = self.engine.enqueue("graph.run", payload)
            return {"status": "queued", "thread_id": thread["id"], "task": record}

        if cmd == "/tasks":
            return {"tasks": self._recent_task_runs()}

        if cmd == "/status":
            task_loop = self._task_loop_status()
            supabase = self._supabase_health()
            n8n = self._n8n_health()

            # Map last task outcome into the same spatial syntax.
            last_event = (task_loop or {}).get("last_event") or {}
            last_task_status = str(last_event.get("status") or "").lower()
            last_task = {"status": last_task_status or "unknown", **self._decorate(last_task_status or "unknown")}
            if last_task_status:
                last_task["ts"] = last_event.get("ts")
                if "error" in last_event:
                    last_task["error"] = last_event.get("error")
                if "retries" in last_event:
                    last_task["retries"] = last_event.get("retries")

            return {
                "overall": self._overall_status(task_loop, supabase, n8n),
                "task_loop": {**task_loop, **self._decorate(task_loop.get("status", "unknown"))},
                "last_task": last_task,
                "supabase": {**supabase, **self._decorate(supabase.get("status", "unknown"))},
                "n8n": {**n8n, **self._decorate(n8n.get("status", "unknown"))},
            }

        return {"status": "unknown_command", "text": text}

    def _default_cron_for(self, workflow: str) -> str:
        defaults = {
            "openclaw-apify-ingest": "0 * * * *",
            "openclaw-retell-dispatch": "10 * * * *",
            "openclaw-nurture-run": "0 10 * * *",
        }
        return defaults.get(workflow, "0 * * * *")

    def _upsert_cron_job(self, workflow: str, cron: str) -> Dict[str, Any]:
        if not self.supabase_url or not self.supabase_key:
            return {"error": "supabase_missing"}
        job = {
            "name": f"cron:{workflow}",
            "cron": cron,
            "task_type": "n8n.trigger",
            "payload_json": {"workflow": workflow, "data": {}},
            "active": True,
            "updated_at": self._now(),
        }
        headers = self._headers()
        headers["Prefer"] = "return=representation,resolution=merge-duplicates"
        try:
            resp = requests.post(
                f"{self.supabase_url}/rest/v1/cron_jobs?on_conflict=name",
                headers=headers,
                data=json.dumps(job),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data[0] if isinstance(data, list) and data else data
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 409:
                return {"error": f"upsert_failed:{exc}"}
            # Last-resort fallback if conflict handling is not accepted by the PostgREST version.
            try:
                patch_headers = self._headers()
                patch_headers["Prefer"] = "return=representation"
                patch = {
                    "cron": cron,
                    "task_type": "n8n.trigger",
                    "payload_json": {"workflow": workflow, "data": {}},
                    "active": True,
                    "updated_at": self._now(),
                }
                patch_resp = requests.patch(
                    f"{self.supabase_url}/rest/v1/cron_jobs?name=eq.{job['name']}",
                    headers=patch_headers,
                    data=json.dumps(patch),
                    timeout=30,
                )
                patch_resp.raise_for_status()
                data = patch_resp.json()
                return data[0] if isinstance(data, list) and data else data
            except requests.RequestException as patch_exc:
                return {"error": f"upsert_conflict:{patch_exc}"}
        except requests.RequestException as exc:
            return {"error": f"upsert_failed:{exc}"}

    def _recent_task_runs(self) -> List[Dict[str, Any]]:
        if not self.supabase_url or not self.supabase_key:
            return []
        params = {"select": "id,task_id,status,started_at,ended_at,error", "order": "created_at.desc", "limit": "5"}
        resp = requests.get(
            f"{self.supabase_url}/rest/v1/task_runs",
            headers=self._headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _task_loop_status(self) -> Dict[str, Any]:
        try:
            path = os.path.expanduser("~/.openclaw-eve/runtime/telemetry.jsonl")
            if not os.path.exists(path):
                return {"status": "no_telemetry"}
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if not lines:
                return {"status": "empty"}
            last = json.loads(lines[-1])
            return {"status": "ok", "last_event": last}
        except Exception as exc:  # pylint: disable=broad-except
            return {"status": "error", "error": str(exc)}

    def _supabase_health(self) -> Dict[str, Any]:
        if not self.supabase_url or not self.supabase_key:
            return {"status": "missing"}
        resp = requests.get(
            f"{self.supabase_url}/rest/v1/tasks?select=id&limit=1",
            headers=self._headers(),
            timeout=15,
        )
        return {"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code}

    def _n8n_health(self) -> Dict[str, Any]:
        if not self.n8n_api_key:
            return {"status": "missing"}
        resp = requests.get(
            f"{self.n8n_api_base}/workflows",
            headers={"X-N8N-API-KEY": self.n8n_api_key},
            timeout=15,
        )
        return {"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code}

    def _decorate(self, status: str) -> Dict[str, Any]:
        """
        Spatial mapping for fast scanning:
        - GREEN: healthy / operating normally
        - RED: down / hard failure
        - YELLOW: degraded / unknown / missing signal
        """
        if status in {"ok", "completed"}:
            return {"color": "GREEN", "meaning": "Operating normally."}
        if status in {"running", "queued"}:
            return {"color": "YELLOW", "meaning": "In progress; waiting for completion."}
        if status in {"failed", "error"}:
            return {"color": "RED", "meaning": "Hard failure; intervention required."}
        if status == "missing":
            return {"color": "YELLOW", "meaning": "Not configured or missing credentials."}
        if status in {"no_telemetry", "empty"}:
            return {"color": "YELLOW", "meaning": "No recent telemetry; cannot confirm health."}
        if status == "down":
            return {"color": "RED", "meaning": "Service unreachable / down."}
        return {"color": "YELLOW", "meaning": "Degraded or unknown state."}

    def _overall_status(self, task_loop: Dict[str, Any], supabase: Dict[str, Any], n8n: Dict[str, Any]) -> Dict[str, Any]:
        # If dependencies are down, overall is red.
        if supabase.get("status") != "ok" or n8n.get("status") != "ok":
            status = "down"
        else:
            last_event = (task_loop or {}).get("last_event") or {}
            last_task_status = str(last_event.get("status") or "").lower()
            if last_task_status == "failed":
                status = "failed"
            else:
                status = "ok"
        return {"status": status, **self._decorate(status)}

    def _headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json", "apikey": self.supabase_key, "Authorization": f"Bearer {self.supabase_key}"}

    def _now(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
