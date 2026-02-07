from __future__ import annotations

import os
from urllib.parse import urlparse
from datetime import datetime, timezone
from typing import Any, Dict

import requests

from .task_registry import TaskHandler, TaskRegistry
from .medspa_launch import MedspaLaunch


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _webhook_candidates(base: str, workflow: str) -> list[str]:
    workflow_path = workflow.lstrip("/")
    base_clean = base.rstrip("/")

    if _is_http_url(workflow):
        return [workflow]

    if "{workflow}" in base_clean:
        return [base_clean.format(workflow=workflow_path)]

    candidates = [f"{base_clean}/{workflow_path}"]
    if "/webhook" not in base_clean:
        candidates.append(f"{base_clean}/webhook/{workflow_path}")
        candidates.append(f"{base_clean}/webhook-test/{workflow_path}")
    return candidates


def handler_n8n_trigger(payload: Dict[str, Any]) -> Dict[str, Any]:
    base = os.environ.get("N8N_PUBLIC_WEBHOOK_BASE", "")
    workflow = payload.get("workflow")
    if not base or not workflow:
        raise RuntimeError("N8N_PUBLIC_WEBHOOK_BASE and payload.workflow are required")
    errors = []
    for url in _webhook_candidates(base, str(workflow)):
        try:
            resp = requests.post(url, json=payload.get("data", {}), timeout=30)
            resp.raise_for_status()
            try:
                return resp.json()
            except ValueError:
                return {"response": resp.text}
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                errors.append(f"404:{url}")
                continue
            raise
        except requests.RequestException as exc:
            errors.append(f"{type(exc).__name__}:{url}")
            continue
    raise RuntimeError(f"n8n webhook failed for workflow={workflow}; attempts={errors}")


def handler_reports_daily(_: Dict[str, Any]) -> Dict[str, Any]:
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
    today = datetime.now(timezone.utc).date().isoformat()
    leads = requests.get(
        f"{supabase_url}/rest/v1/leads?select=id,created_at&created_at=gte.{today}",
        headers=headers,
        timeout=30,
    ).json()
    calls = requests.get(
        f"{supabase_url}/rest/v1/call_sessions?select=id,created_at&created_at=gte.{today}",
        headers=headers,
        timeout=30,
    ).json()
    segments = requests.get(
        f"{supabase_url}/rest/v1/segments?select=segment,last_updated&last_updated=gte.{today}",
        headers=headers,
        timeout=30,
    ).json()
    return {
        "date": today,
        "leads": len(leads),
        "call_sessions": len(calls),
        "segments": len(segments),
    }


def handler_graph_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    from .graph_runner import run_graph
    graph = payload.get("graph", {})
    context = payload.get("context", {})
    thread_name = payload.get("thread_name", "graph")
    ledger_path = os.path.expanduser("~/.openclaw-eve/omega/ledger.jsonl")
    return run_graph(graph, context, thread_name, ledger_path)


def handler_medspa_launch(payload: Dict[str, Any]) -> Dict[str, Any]:
    launcher = MedspaLaunch()
    return launcher.launch(payload)


def build_registry() -> TaskRegistry:
    registry = TaskRegistry()
    registry.register("n8n.trigger", TaskHandler("n8n.trigger", handler_n8n_trigger))
    registry.register("reports.daily", TaskHandler("reports.daily", handler_reports_daily))
    registry.register("graph.run", TaskHandler("graph.run", handler_graph_run))
    registry.register("medspa.launch", TaskHandler("medspa.launch", handler_medspa_launch))
    return registry


def handler_map() -> Dict[str, Any]:
    return {
        "n8n.trigger": handler_n8n_trigger,
        "reports.daily": handler_reports_daily,
        "graph.run": handler_graph_run,
        "medspa.launch": handler_medspa_launch,
    }
