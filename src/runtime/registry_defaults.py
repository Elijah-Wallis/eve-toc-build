from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict

import requests

from .task_registry import TaskHandler, TaskRegistry
from .medspa_launch import MedspaLaunch
from .n8n_webhooks import post_with_auto_heal
from .postcall_reconciler import PostcallReconciler
from .runtime_paths import state_path


def handler_n8n_trigger(payload: Dict[str, Any]) -> Dict[str, Any]:
    base = os.environ.get("N8N_PUBLIC_WEBHOOK_BASE", "")
    n8n_api_base = os.environ.get("N8N_API_BASE", "https://elijah-wallis.app.n8n.cloud/api/v1")
    n8n_api_key = os.environ.get("N8N_API_KEY", "")
    workflow = payload.get("workflow")
    if not base or not workflow:
        raise RuntimeError("N8N_PUBLIC_WEBHOOK_BASE and payload.workflow are required")
    result = post_with_auto_heal(
        webhook_base=base,
        workflow_path=str(workflow),
        data=payload.get("data", {}),
        timeout=30,
        n8n_api_base=n8n_api_base,
        n8n_api_key=n8n_api_key,
    )
    status_code = int(result.get("status_code") or 0)
    if status_code >= 400:
        raise RuntimeError(f"n8n webhook failed for workflow={workflow}; status={status_code}; url={result.get('url')}")
    return result.get("body") if isinstance(result.get("body"), dict) else {"response": result.get("body")}


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
    ledger_path = str(state_path("omega", "ledger.jsonl"))
    return run_graph(graph, context, thread_name, ledger_path)


def handler_medspa_launch(payload: Dict[str, Any]) -> Dict[str, Any]:
    launcher = MedspaLaunch()
    return launcher.launch(payload)


def handler_medspa_ramp(payload: Dict[str, Any]) -> Dict[str, Any]:
    launcher = MedspaLaunch()
    return launcher.approve_ramp(payload)


def handler_retell_postcall_reconcile(payload: Dict[str, Any]) -> Dict[str, Any]:
    reconciler = PostcallReconciler()
    return reconciler.reconcile(payload)


def build_registry() -> TaskRegistry:
    registry = TaskRegistry()
    registry.register("n8n.trigger", TaskHandler("n8n.trigger", handler_n8n_trigger))
    registry.register("reports.daily", TaskHandler("reports.daily", handler_reports_daily))
    registry.register("graph.run", TaskHandler("graph.run", handler_graph_run))
    registry.register("medspa.launch", TaskHandler("medspa.launch", handler_medspa_launch))
    registry.register("medspa.ramp", TaskHandler("medspa.ramp", handler_medspa_ramp))
    registry.register(
        "retell.postcall.reconcile",
        TaskHandler("retell.postcall.reconcile", handler_retell_postcall_reconcile),
    )
    return registry


def handler_map() -> Dict[str, Any]:
    return {
        "n8n.trigger": handler_n8n_trigger,
        "reports.daily": handler_reports_daily,
        "graph.run": handler_graph_run,
        "medspa.launch": handler_medspa_launch,
        "medspa.ramp": handler_medspa_ramp,
        "retell.postcall.reconcile": handler_retell_postcall_reconcile,
    }
