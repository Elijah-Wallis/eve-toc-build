#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
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
    "EVIDENCE_EMAIL_API_KEY",
}


def _binding_mode() -> str:
    # Deprecated: dashboard enforces env/vars bindings regardless of runtime mode.
    # Keep for backward-compat reporting only.
    return "env_or_vars"


def _is_valid_secret_binding(value: str) -> bool:
    stripped = value.strip()
    return stripped.startswith("={{$env.") or stripped.startswith("={{$vars.")


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
            if not _is_valid_secret_binding(value):
                reason = "empty_value" if not value.strip() else "literal_or_invalid_binding"
                findings.append(
                    {
                        "source": source,
                        "workflow": str(workflow.get("name") or "unknown"),
                        "key": key,
                        "reason": reason,
                    }
                )
    return findings


def main() -> int:
    prefix = os.environ.get("OPENCLAW_WORKFLOW_PREFIX", "openclaw_")
    findings: List[Dict[str, str]] = []
    scanned = 0

    for path in sorted(WORKFLOWS_DIR.glob("*.json")):
        wf = json.loads(path.read_text(encoding="utf-8"))
        name = str(wf.get("name") or "")
        if prefix and not name.startswith(prefix):
            continue
        scanned += 1
        findings.extend(_scan_workflow_nodes(wf, f"local:{path.name}"))

    report = {
        "ok": len(findings) == 0,
        "binding_mode": _binding_mode(),
        "workflows_scanned": scanned,
        "findings": findings,
    }
    print(json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
