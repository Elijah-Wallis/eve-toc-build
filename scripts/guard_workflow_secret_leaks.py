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

SENSITIVE_CONFIG_KEYS = {
    "SUPABASE_SERVICE_ROLE_KEY",
    "RETELL_AI_KEY",
    "TWILIO_AUTH_TOKEN",
    "APIFY_API_TOKEN",
    "N8N_API_KEY",
    "N8N_MCP_TOKEN",
    "N8N_MCP_ACCESS_TOKEN",
    "OPENCLAW_TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BOT_TOKEN",
}


def _is_env_expr(value: str) -> bool:
    return value.strip().startswith("={{$env.")


def _scan_workflow_nodes(workflow: Dict[str, Any], source: str) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    for node in workflow.get("nodes", []):
        if node.get("type") != "n8n-nodes-base.set" or node.get("name") != "Config":
            continue
        rows = (((node.get("parameters") or {}).get("values") or {}).get("string") or [])
        for row in rows:
            key = str(row.get("name") or "")
            if key not in SENSITIVE_CONFIG_KEYS:
                continue
            value = str(row.get("value") or "")
            if not _is_env_expr(value):
                findings.append(
                    {
                        "source": source,
                        "workflow": str(workflow.get("name") or "unknown"),
                        "key": key,
                    }
                )
    return findings


def _scan_local(prefix: str) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    for path in sorted(WORKFLOWS_DIR.glob("*.json")):
        wf = json.loads(path.read_text(encoding="utf-8"))
        name = str(wf.get("name") or "")
        if prefix and not name.startswith(prefix):
            continue
        findings.extend(_scan_workflow_nodes(wf, f"local:{path.name}"))
    return findings


def _n8n_headers() -> Dict[str, str]:
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        raise RuntimeError("N8N_API_KEY is required for --check-remote")
    return {"X-N8N-API-KEY": key, "Accept": "application/json"}


def _n8n_base() -> str:
    return os.environ.get("N8N_API_BASE", "https://elijah-wallis.app.n8n.cloud/api/v1").rstrip("/")


def _scan_remote(prefix: str) -> Tuple[List[Dict[str, str]], int]:
    rows = requests.get(f"{_n8n_base()}/workflows", headers=_n8n_headers(), timeout=30).json().get("data", [])
    findings: List[Dict[str, str]] = []
    scanned = 0
    for row in rows:
        wid = row.get("id")
        name = str(row.get("name") or "")
        if not wid or (prefix and not name.startswith(prefix)):
            continue
        detail = requests.get(f"{_n8n_base()}/workflows/{wid}", headers=_n8n_headers(), timeout=30).json()
        wf = detail.get("data", detail)
        scanned += 1
        findings.extend(_scan_workflow_nodes(wf, f"remote:{wid}"))
    return findings, scanned


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-fast guard for literal secrets in workflow Config nodes.")
    parser.add_argument("--check-remote", action="store_true", help="Also scan remote n8n workflows via API")
    parser.add_argument("--prefix", default="openclaw_", help="Workflow name prefix to scan")
    parser.add_argument("--allow-findings", action="store_true", help="Always return 0 even when findings exist")
    args = parser.parse_args()

    local_findings = _scan_local(args.prefix)
    remote_findings: List[Dict[str, str]] = []
    remote_scanned = 0
    if args.check_remote:
        remote_findings, remote_scanned = _scan_remote(args.prefix)

    findings = local_findings + remote_findings
    report = {
        "ok": len(findings) == 0,
        "local_findings": local_findings,
        "remote_findings": remote_findings,
        "counts": {
            "local_findings": len(local_findings),
            "remote_findings": len(remote_findings),
            "remote_workflows_scanned": remote_scanned,
        },
    }
    print(json.dumps(report, ensure_ascii=True))
    if findings and not args.allow_findings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
