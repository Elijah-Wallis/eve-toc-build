#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List

import requests


TARGET_NAMES = [
    "openclaw_retell_call_dispatch",
    "openclaw_nurture_engine",
    "openclaw_retell_postcall_ingest",
    "openclaw_apify_scrape_ingest",
]


def _api_base() -> str:
    return os.environ.get("N8N_API_BASE", "https://elijah-wallis.app.n8n.cloud/api/v1").rstrip("/")


def _headers() -> Dict[str, str]:
    api_key = os.environ.get("N8N_API_KEY", "")
    if not api_key:
        raise RuntimeError("N8N_API_KEY is required")
    return {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}


def _list_workflows() -> List[Dict[str, Any]]:
    resp = requests.get(f"{_api_base()}/workflows", headers=_headers(), timeout=30)
    resp.raise_for_status()
    body = resp.json()
    return body.get("data", body if isinstance(body, list) else [])


def _get_workflow(wid: str) -> Dict[str, Any]:
    resp = requests.get(f"{_api_base()}/workflows/{wid}", headers=_headers(), timeout=30)
    resp.raise_for_status()
    body = resp.json()
    return body.get("data", body)


def _update_workflow(wid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.put(
        f"{_api_base()}/workflows/{wid}",
        headers=_headers(),
        data=json.dumps(payload),
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    return body.get("data", body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure selected n8n workflows are available in MCP.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    indexed = {wf.get("name"): wf.get("id") for wf in _list_workflows() if wf.get("name") and wf.get("id")}
    report: Dict[str, Any] = {"updated": [], "unchanged": [], "missing": []}
    for name in TARGET_NAMES:
        wid = indexed.get(name)
        if not wid:
            report["missing"].append(name)
            continue

        detail = _get_workflow(wid)
        settings = dict(detail.get("settings") or {})
        if settings.get("availableInMCP") is True:
            report["unchanged"].append({"id": wid, "name": name})
            continue

        settings["availableInMCP"] = True
        update_payload = {
            "name": detail.get("name"),
            "nodes": detail.get("nodes"),
            "connections": detail.get("connections"),
            "settings": settings,
        }
        if not args.dry_run:
            _update_workflow(wid, update_payload)
        report["updated"].append({"id": wid, "name": name, "dry_run": bool(args.dry_run)})

    print(json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
