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

BINDING_SPECS: Dict[str, Dict[str, Any]] = {
    "SUPABASE_URL": {"env": "SUPABASE_URL"},
    "SUPABASE_SERVICE_ROLE_KEY": {"env": "SUPABASE_SERVICE_ROLE_KEY"},
    "RETELL_AI_KEY": {"env": "RETELL_AI_KEY"},
    "RETELL_FROM_NUMBER": {"env": "RETELL_FROM_NUMBER"},
    "RETELL_AGENT_B2B_ID": {"env": "RETELL_AGENT_B2B_ID"},
    "RETELL_AGENT_B2C_ID": {"env": "RETELL_AGENT_B2C_ID"},
    "TWILIO_ACCOUNT_SID": {"env": "TWILIO_ACCOUNT_SID"},
    "TWILIO_AUTH_TOKEN": {"env": "TWILIO_AUTH_TOKEN"},
    "TWILIO_FROM_NUMBER": {"env": "TWILIO_FROM_NUMBER"},
    "APIFY_API_TOKEN": {"env": "APIFY_API_TOKEN"},
    "APIFY_ACTOR_ID": {"env": "APIFY_ACTOR_ID", "default": "compass/crawler-google-places"},
    "N8N_PUBLIC_WEBHOOK_BASE": {"env": "N8N_PUBLIC_WEBHOOK_BASE", "default": "https://elijah-wallis.app.n8n.cloud"},
    "OPENCLAW_TELEGRAM_BOT_TOKEN": {"fallback_envs": ["TELEGRAM_BOT_TOKEN", "OPENCLAW_TELEGRAM_BOT_TOKEN"]},
    "OPENCLAW_TELEGRAM_CHAT_ID": {"env": "OPENCLAW_TELEGRAM_CHAT_ID", "default": ""},
    "B2C_CLINIC_NAME": {"env": "B2C_CLINIC_NAME", "default": "Your MedSpa"},
    "B2C_TIMEZONE": {"env": "B2C_TIMEZONE", "default": "America/Chicago"},
    "B2C_OPEN_HOUR": {"env": "B2C_OPEN_HOUR", "default": "9"},
    "B2C_CLOSE_HOUR": {"env": "B2C_CLOSE_HOUR", "default": "18"},
    "B2C_CREDENTIALS_BLURB": {
        "env": "B2C_CREDENTIALS_BLURB",
        "default": "Board-certified clinical team and medical director oversight",
    },
    "NURTURE_SMS_ENABLED": {"env": "NURTURE_SMS_ENABLED", "default": "0"},
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


def _binding_expr(name: str, mode: str) -> str | None:
    spec = BINDING_SPECS.get(name) or {}
    env_name = str(spec.get("env") or name)
    default = spec.get("default")
    fallback_envs = list(spec.get("fallback_envs") or [])

    if mode == "env":
        if fallback_envs:
            joined = " || ".join(f"$env.{candidate}" for candidate in fallback_envs)
            return "={{" + joined + "}}"
        if default is None:
            return "={{$env." + env_name + "}}"
        escaped = str(default).replace("'", "\\'")
        return "={{$env." + env_name + " || '" + escaped + "'}}"

    if mode == "vars":
        if fallback_envs:
            joined = " || ".join(f"$vars.{candidate}" for candidate in fallback_envs)
            return "={{" + joined + "}}"
        if default is None:
            return "={{$vars." + env_name + "}}"
        escaped = str(default).replace("'", "\\'")
        return "={{$vars." + env_name + " || '" + escaped + "'}}"

    if mode == "literal":
        for candidate in fallback_envs:
            value = os.environ.get(candidate, "")
            if value:
                return value
        value = os.environ.get(env_name, "")
        if value:
            return value
        if default is not None:
            return str(default)
        return ""

    raise RuntimeError(f"unsupported mode: {mode}")


def _patch_workflow(workflow: Dict[str, Any], mode: str) -> Tuple[Dict[str, Any], List[str]]:
    touched: List[str] = []
    for node in workflow.get("nodes", []):
        if node.get("type") == "n8n-nodes-base.set" and node.get("name") == "Config":
            values = ((node.get("parameters") or {}).get("values") or {})
            strings = values.get("string") or []
            existing_names = {str(row.get("name") or "") for row in strings}
            for row in strings:
                name = row.get("name")
                if not name or name not in BINDING_SPECS:
                    continue
                expected = _binding_expr(str(name), mode)
                if expected is None:
                    continue
                if row.get("value") != expected:
                    row["value"] = expected
                    touched.append(str(name))
            if "NURTURE_SMS_ENABLED" not in existing_names:
                sms_expected = _binding_expr("NURTURE_SMS_ENABLED", mode)
                if sms_expected is not None:
                    strings.append({"name": "NURTURE_SMS_ENABLED", "value": sms_expected})
                    touched.append("NURTURE_SMS_ENABLED")
            continue

        # n8n Cloud blocks $env in code node context; use Config node values instead.
        if node.get("type") == "n8n-nodes-base.function" and node.get("name") == "Build SMS":
            parameters = node.get("parameters") or {}
            code = str(parameters.get("functionCode") or "")
            if "$env." in code:
                code = code.replace("$env.TWILIO_ACCOUNT_SID", "$node[\"Config\"].json.TWILIO_ACCOUNT_SID")
                code = code.replace("$env.TWILIO_AUTH_TOKEN", "$node[\"Config\"].json.TWILIO_AUTH_TOKEN")
                code = code.replace("$env.TWILIO_FROM_NUMBER", "$node[\"Config\"].json.TWILIO_FROM_NUMBER")
                code = code.replace("$env.AUDIT_REPORT_URL", "$node[\"Config\"].json.AUDIT_REPORT_URL")
                parameters["functionCode"] = code
                node["parameters"] = parameters
                touched.append("Build SMS:functionCode")
            continue

        if node.get("type") == "n8n-nodes-base.function" and node.get("name") == "Plan Touch":
            parameters = node.get("parameters") or {}
            code = str(parameters.get("functionCode") or "")
            changed = False
            marker = "const smsEnabled = String($node[\"Config\"].json.NURTURE_SMS_ENABLED || '0') === '1';\n"
            if marker not in code:
                code = code.replace("const maxTouches = 8;\n", "const maxTouches = 8;\n  " + marker, 1)
                changed = True
            target = "if (lead.positive_signal && lead.phone && $node[\"Config\"].json.TWILIO_FROM_NUMBER) action = 'VALUE_SMS';"
            replacement = (
                "if (smsEnabled && lead.positive_signal && lead.phone && $node[\"Config\"].json.TWILIO_FROM_NUMBER) action = 'VALUE_SMS';"
            )
            if target in code:
                code = code.replace(target, replacement, 1)
                changed = True
            if changed:
                parameters["functionCode"] = code
                node["parameters"] = parameters
                touched.append("Plan Touch:functionCode")
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


def _update_remote_workflow(workflow_id: str, workflow: Dict[str, Any]) -> None:
    nodes = workflow.get("nodes") or []
    if not nodes:
        raise RuntimeError(f"refusing to update workflow {workflow_id} with empty node set")
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
    parser = argparse.ArgumentParser(description="Patch n8n workflow Config bindings (env/vars/literal).")
    parser.add_argument("--apply-remote", action="store_true", help="Also patch matching workflows in remote n8n")
    parser.add_argument("--remote-only", action="store_true", help="Patch remote workflows only; do not edit local files")
    parser.add_argument("--prefix", default="openclaw_", help="Workflow name prefix to patch")
    parser.add_argument(
        "--mode",
        choices=["env", "vars", "literal"],
        default="env",
        help="Binding mode for Config values",
    )
    args = parser.parse_args()

    local_report: List[Dict[str, Any]] = []
    if not args.remote_only:
        for path in _workflow_files():
            wf = _read_json(path)
            name = str(wf.get("name") or "")
            if args.prefix and not name.startswith(args.prefix):
                continue
            patched, touched = _patch_workflow(wf, args.mode)
            if touched:
                _write_json(path, patched)
            local_report.append({"file": str(path), "patched_keys": sorted(set(touched))})

    remote_report: List[Dict[str, Any]] = []
    if args.apply_remote:
        remote_index = _list_remote_workflows()
        local_by_name: Dict[str, Dict[str, Any]] = {}
        for path in _workflow_files():
            wf = _read_json(path)
            name = str(wf.get("name") or "")
            if not name:
                continue
            local_by_name[name] = wf
        if args.remote_only:
            target_names = sorted(n for n in remote_index.keys() if (not args.prefix or n.startswith(args.prefix)))
        else:
            local_names = {(_read_json(path).get("name") or "") for path in _workflow_files()}
            target_names = sorted(n for n in local_names if n and (not args.prefix or n.startswith(args.prefix)))
        for name in target_names:
            workflow_id = remote_index.get(name)
            if not workflow_id:
                remote_report.append({"name": name, "status": "missing"})
                continue
            source_wf = local_by_name.get(name)
            if not source_wf:
                remote_report.append({"name": name, "id": workflow_id, "status": "missing_local_source"})
                continue
            patched_remote, touched = _patch_workflow(source_wf, args.mode)
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
                except Exception as exc:  # noqa: BLE001
                    remote_report.append(
                        {
                            "name": name,
                            "id": workflow_id,
                            "status": "error",
                            "error": str(exc),
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
        "mode": args.mode,
        "remote_only": bool(args.remote_only),
        "local": local_report,
        "remote": remote_report,
    }
    print(json.dumps(output, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
