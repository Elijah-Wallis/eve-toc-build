#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = ROOT / "workflows_n8n"
MODE = os.environ.get("OPENCLAW_N8N_BINDING_MODE", "env").strip().lower()
ALLOW_LITERAL_RUNTIME = os.environ.get("OPENCLAW_ALLOW_LITERAL_WORKFLOW_SECRETS", "0") == "1"

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
    "EVIDENCE_EMAIL_API_KEY",
}

REQUIRED_ACTIVE_WORKFLOWS = {
    "openclaw_retell_postcall_ingest",
}

REQUIRED_WORKFLOW_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "openclaw_retell_fn_send_evidence_package": {
        "webhook_path": "openclaw-retell-fn-send-evidence-package",
        "config_keys": {
            "SUPABASE_URL",
            "SUPABASE_SERVICE_ROLE_KEY",
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "TWILIO_FROM_NUMBER",
            "EVIDENCE_EMAIL_PROVIDER_URL",
            "EVIDENCE_EMAIL_API_KEY",
            "EVIDENCE_EMAIL_FROM",
        },
    }
}


def _load_workflow(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_secret_binding(value: str) -> bool:
    text = str(value or "").strip()
    if MODE == "env":
        return text.startswith("={{$env.")
    if MODE == "vars":
        return text.startswith("={{$vars.")
    if MODE == "literal":
        if ALLOW_LITERAL_RUNTIME:
            return bool(text)
        return bool(text) and not text.startswith("={{$env.") and not text.startswith("={{$vars.")
    return False


def _scan(path: Path, wf: Dict[str, Any]) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    workflow_name = str(wf.get("name") or path.name)
    if workflow_name in REQUIRED_ACTIVE_WORKFLOWS and not bool(wf.get("active")):
        findings.append(
            {
                "kind": "workflow_inactive",
                "workflow": workflow_name,
            }
        )
    for node in wf.get("nodes", []):
        node_name = str(node.get("name") or "")
        node_type = str(node.get("type") or "")
        if node_type == "n8n-nodes-base.webhook":
            webhook_id = str(node.get("webhookId") or "").strip()
            webhook_path = str(((node.get("parameters") or {}).get("path") or "")).strip()
            if webhook_path and not webhook_id:
                findings.append(
                    {
                        "kind": "missing_webhook_id",
                        "workflow": workflow_name,
                        "node": node_name,
                        "path": webhook_path,
                    }
                )
        if node_type == "n8n-nodes-base.set" and node_name == "Config":
            rows = (((node.get("parameters") or {}).get("values") or {}).get("string") or [])
            if workflow_name in REQUIRED_WORKFLOW_CONTRACTS:
                required = set(REQUIRED_WORKFLOW_CONTRACTS[workflow_name].get("config_keys") or set())
                present = {str(row.get("name") or "") for row in rows}
                missing = sorted(required - present)
                for key in missing:
                    findings.append(
                        {
                            "kind": "missing_required_config_key",
                            "workflow": workflow_name,
                            "node": node_name,
                            "key": key,
                        }
                    )
            for row in rows:
                key = str(row.get("name") or "")
                if key not in SENSITIVE_CONFIG_KEYS:
                    continue
                value = str(row.get("value") or "")
                if not _valid_secret_binding(value):
                    findings.append(
                        {
                            "kind": "invalid_secret_binding",
                            "workflow": workflow_name,
                            "node": node_name,
                            "key": key,
                        }
                    )
    if workflow_name in REQUIRED_WORKFLOW_CONTRACTS:
        expected_path = str(REQUIRED_WORKFLOW_CONTRACTS[workflow_name].get("webhook_path") or "")
        webhook_paths = [
            str(((node.get("parameters") or {}).get("path") or "")).strip()
            for node in wf.get("nodes", [])
            if str(node.get("type") or "") == "n8n-nodes-base.webhook"
        ]
        if expected_path and expected_path not in webhook_paths:
            findings.append(
                {
                    "kind": "missing_required_webhook_path",
                    "workflow": workflow_name,
                    "path": expected_path,
                }
            )
    return findings


def main() -> int:
    findings: List[Dict[str, str]] = []
    checked = 0
    for path in sorted(WORKFLOWS_DIR.glob("*.json")):
        wf = _load_workflow(path)
        checked += 1
        findings.extend(_scan(path, wf))
    report = {
        "ok": len(findings) == 0,
        "binding_mode": MODE,
        "allow_literal_runtime": ALLOW_LITERAL_RUNTIME,
        "workflows_checked": checked,
        "finding_count": len(findings),
        "findings": findings[:200],
    }
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
