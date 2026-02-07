#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = ROOT / "workflows_n8n"

# Force these config values to env expressions to prevent static secret leakage.
ENV_BINDINGS: Dict[str, str] = {
    "SUPABASE_URL": "={{$env.SUPABASE_URL}}",
    "SUPABASE_SERVICE_ROLE_KEY": "={{$env.SUPABASE_SERVICE_ROLE_KEY}}",
    "RETELL_AI_KEY": "={{$env.RETELL_AI_KEY}}",
    "RETELL_FROM_NUMBER": "={{$env.RETELL_FROM_NUMBER}}",
    "RETELL_AGENT_B2B_ID": "={{$env.RETELL_AGENT_B2B_ID}}",
    "RETELL_AGENT_B2C_ID": "={{$env.RETELL_AGENT_B2C_ID}}",
    "TWILIO_ACCOUNT_SID": "={{$env.TWILIO_ACCOUNT_SID}}",
    "TWILIO_AUTH_TOKEN": "={{$env.TWILIO_AUTH_TOKEN}}",
    "TWILIO_FROM_NUMBER": "={{$env.TWILIO_FROM_NUMBER}}",
    "APIFY_API_TOKEN": "={{$env.APIFY_API_TOKEN}}",
    "APIFY_ACTOR_ID": "={{$env.APIFY_ACTOR_ID || 'compass/crawler-google-places'}}",
    "N8N_PUBLIC_WEBHOOK_BASE": "={{$env.N8N_PUBLIC_WEBHOOK_BASE || 'https://elijah-wallis.app.n8n.cloud'}}",
    "OPENCLAW_TELEGRAM_BOT_TOKEN": "={{$env.TELEGRAM_BOT_TOKEN || $env.OPENCLAW_TELEGRAM_BOT_TOKEN}}",
    "OPENCLAW_TELEGRAM_CHAT_ID": "={{$env.OPENCLAW_TELEGRAM_CHAT_ID || ''}}",
}


def _headers() -> Dict[str, str]:
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        raise RuntimeError("N8N_API_KEY is required")
    return {"X-N8N-API-KEY": key, "Content-Type": "application/json", "Accept": "application/json"}


def _base() -> str:
    return os.environ.get("N8N_API_BASE", "https://elijah-wallis.app.n8n.cloud/api/v1").rstrip("/")


def _workflow_files() -> List[Path]:
    return sorted(p for p in WORKFLOWS_DIR.glob("*.json") if p.is_file())


def _patch_workflow(workflow: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    touched: List[str] = []
    for node in workflow.get("nodes", []):
        if node.get("type") != "n8n-nodes-base.set" or node.get("name") != "Config":
            continue
        values = ((node.get("parameters") or {}).get("values") or {})
        strings = values.get("string") or []
        for row in strings:
            name = row.get("name")
            if not name or name not in ENV_BINDINGS:
                continue
            expected = ENV_BINDINGS[name]
            if row.get("value") != expected:
                row["value"] = expected
                touched.append(name)
    return workflow, touched


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _list_remote_workflows() -> Dict[str, str]:
    resp = requests.get(f"{_base()}/workflows", headers=_headers(), timeout=30)
    resp.raise_for_status()
    rows = resp.json().get("data", [])
    return {row.get("name"): row.get("id") for row in rows if row.get("name") and row.get("id")}


def _get_remote_workflow(workflow_id: str) -> Dict[str, Any]:
    resp = requests.get(f"{_base()}/workflows/{workflow_id}", headers=_headers(), timeout=30)
    resp.raise_for_status()
    body = resp.json()
    return body.get("data", body)


def _update_remote_workflow(workflow_id: str, workflow: Dict[str, Any]) -> None:
    raw_settings = workflow.get("settings") or {}
    allowed_settings = {
        "timezone",
        "saveExecutionProgress",
        "saveManualExecutions",
        "callerPolicy",
        "availableInMCP",
        "executionTimeout",
        "errorWorkflow",
    }
    settings = {k: v for k, v in raw_settings.items() if k in allowed_settings}
    payload = {
        "name": workflow.get("name"),
        "nodes": workflow.get("nodes"),
        "connections": workflow.get("connections"),
        "settings": settings,
    }
    resp = requests.put(f"{_base()}/workflows/{workflow_id}", headers=_headers(), json=payload, timeout=30)
    resp.raise_for_status()


def main() -> int:
    parser = argparse.ArgumentParser(description="Replace Config literals with env expressions in n8n workflows.")
    parser.add_argument("--apply-remote", action="store_true", help="Also patch matching workflows in remote n8n")
    args = parser.parse_args()

    local_report: List[Dict[str, Any]] = []
    for path in _workflow_files():
        wf = _read_json(path)
        patched, touched = _patch_workflow(wf)
        if touched:
            _write_json(path, patched)
        local_report.append({"file": str(path), "patched_keys": sorted(set(touched))})

    remote_report: List[Dict[str, Any]] = []
    if args.apply_remote:
        remote_index = _list_remote_workflows()
        local_names = {(_read_json(path).get("name") or "") for path in _workflow_files()}
        for name in sorted(n for n in local_names if n):
            workflow_id = remote_index.get(name)
            if not workflow_id:
                remote_report.append({"name": name, "status": "missing"})
                continue
            remote_wf = _get_remote_workflow(workflow_id)
            patched_remote, touched = _patch_workflow(remote_wf)
            if touched:
                try:
                    _update_remote_workflow(workflow_id, patched_remote)
                except requests.HTTPError as exc:
                    body = ""
                    if exc.response is not None:
                        body = (exc.response.text or "")[:300]
                    remote_report.append(
                        {
                            "name": name,
                            "id": workflow_id,
                            "status": "error",
                            "error": body or str(exc),
                            "patched_keys": sorted(set(touched)),
                        }
                    )
                    continue
                remote_report.append(
                    {"name": name, "id": workflow_id, "status": "updated", "patched_keys": sorted(set(touched))}
                )
            else:
                remote_report.append({"name": name, "id": workflow_id, "status": "unchanged"})

    output = {
        "local": local_report,
        "remote": remote_report,
    }
    print(json.dumps(output, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
