#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import requests


ROOT = Path(__file__).resolve().parents[1]
DISPATCH_FILE = ROOT / "workflows_n8n" / "openclaw_retell_call_dispatch.json"
NURTURE_FILE = ROOT / "workflows_n8n" / "openclaw_nurture_engine.json"


DISPATCH_FETCH_LEADS_URL = (
    '={{$node["Config"].json.SUPABASE_URL}}/rest/v1/leads?'
    'select=id,place_id,business_name,phone,email,city,state,zip,status,source,lead_type,decision_maker_confirmed,'
    'positive_signal,touch_count,first_contacted_at,last_contacted_at,paused_until'
    '&status=in.(NEW,NURTURE,RETRY,HOLD)&phone=not.is.null'
    '{{$node["Webhook Trigger"].json.source_filter ? \'&source=eq.\' + encodeURIComponent($node["Webhook Trigger"].json.source_filter) : \'\'}}'
    '&order=created_at.asc&limit={{$node["Webhook Trigger"].json.lead_limit || 25}}'
)

DISPATCH_DAILY_CAP_EXPR = (
    '={{Number($json.count || 0) < Number($node["Webhook Trigger"].json.max_calls || '
    '$node["Config"].json.MAX_CALLS_PER_DAY || 50)}}'
)

DISPATCH_DAILY_CALLS_URL = (
    '={{$node["Config"].json.SUPABASE_URL}}/rest/v1/call_sessions?select=count&created_at=gte.'
    '{{new Date().toISOString().slice(0,10)}}T00:00:00.000Z'
)

NURTURE_FETCH_LEADS_URL = (
    '={{$node["Config"].json.SUPABASE_URL}}/rest/v1/leads?'
    'select=id,place_id,business_name,phone,email,city,state,zip,status,source,lead_type,decision_maker_confirmed,'
    'positive_signal,touch_count,first_contacted_at,last_contacted_at,next_touch_at,paused_until'
    '&status=in.(NEW,NURTURE,RETRY,HOLD,QUALIFIED)'
    '{{$node["Manual Webhook"].json.source_filter ? \'&source=eq.\' + encodeURIComponent($node["Manual Webhook"].json.source_filter) : \'\'}}'
    '&order=created_at.asc&limit={{$node["Manual Webhook"].json.lead_limit || 200}}'
)

DISPATCH_STOPLIST_URL = (
    '={{$node["Config"].json.SUPABASE_URL}}/rest/v1/stoplist?select=count&phone=eq.{{$json.phone}}&limit=1'
)

DISPATCH_STOPLIST_ALLOW_EXPR = '={{Number($json.count || 0)}}'

DISPATCH_FILTER_LEADS_FUNCTION = (
    "const now = new Date();\n"
    "const minHours = Number($node[\"Config\"].json.MIN_HOURS_BETWEEN_TOUCHES || 72);\n"
    "return items.filter((item) => {\n"
    "  const lead = item.json || {};\n"
    "  if (!lead.phone) return false;\n"
    "  if (lead.paused_until && new Date(lead.paused_until) > now) return false;\n"
    "  const touches = lead.touch_count || 0;\n"
    "  if (touches >= 8) return false;\n"
    "  if (lead.last_contacted_at) {\n"
    "    const diffMs = now - new Date(lead.last_contacted_at);\n"
    "    if (diffMs < minHours * 3600 * 1000) return false;\n"
    "  }\n"
    "  return true;\n"
    "});"
)

DISPATCH_BUILD_CALL_PAYLOAD_FUNCTION = (
    "const lead = $node[\"Filter Leads\"].json || {};\n"
    "const agentType = lead.decision_maker_confirmed ? 'B2C' : 'B2B';\n"
    "const agentId = agentType === 'B2C' ? $node[\"Config\"].json.RETELL_AGENT_B2C_ID : "
    "$node[\"Config\"].json.RETELL_AGENT_B2B_ID;\n"
    "const fromNumber = $node[\"Config\"].json.RETELL_FROM_NUMBER;\n"
    "if (!fromNumber || !lead.phone) return [];\n"
    "return [{ json: {\n"
    "  lead,\n"
    "  agent_id: agentId,\n"
    "  agent_type: agentType,\n"
    "  from_number: fromNumber,\n"
    "  request_body: {\n"
    "    from_number: fromNumber,\n"
    "    to_number: lead.phone,\n"
    "    override_agent_id: agentId,\n"
    "    retell_llm_dynamic_variables: {\n"
    "      business_name: lead.business_name || '',\n"
    "      city: lead.city || '',\n"
    "      state: lead.state || '',\n"
    "      website: lead.website || '',\n"
    "      category: Array.isArray(lead.categories) ? (lead.categories[0] || '') : '',\n"
    "      rating: String(lead.rating ?? ''),\n"
    "      reviews_count: String(lead.reviews_count ?? ''),\n"
    "      touch_count: String(lead.touch_count ?? 0),\n"
    "      lead_id: lead.id || '',\n"
    "      source: lead.source || ''\n"
    "    }\n"
    "  }\n"
    "} }];"
)

DISPATCH_RETELL_JSON_BODY_EXPR = "={{$json.request_body}}"


def _find_node(workflow: Dict[str, Any], name: str) -> Dict[str, Any]:
    for node in workflow.get("nodes", []):
        if node.get("name") == name:
            return node
    raise KeyError(f"node not found: {name}")


def _patch_dispatch(workflow: Dict[str, Any]) -> Dict[str, Any]:
    fetch = _find_node(workflow, "Fetch Leads")
    fetch["parameters"]["url"] = DISPATCH_FETCH_LEADS_URL
    daily = _find_node(workflow, "Fetch Daily Calls")
    daily["parameters"]["url"] = DISPATCH_DAILY_CALLS_URL
    cap = _find_node(workflow, "Under Daily Cap?")
    cap["parameters"]["conditions"]["boolean"][0]["value1"] = DISPATCH_DAILY_CAP_EXPR
    stop = _find_node(workflow, "Check Stoplist")
    stop["parameters"]["url"] = DISPATCH_STOPLIST_URL
    stop_if = _find_node(workflow, "Not In Stoplist?")
    stop_if["parameters"]["conditions"]["number"][0]["value1"] = DISPATCH_STOPLIST_ALLOW_EXPR
    filt = _find_node(workflow, "Filter Leads")
    filt["parameters"]["functionCode"] = DISPATCH_FILTER_LEADS_FUNCTION
    build = _find_node(workflow, "Build Call Payload")
    build["parameters"]["functionCode"] = DISPATCH_BUILD_CALL_PAYLOAD_FUNCTION
    retell = _find_node(workflow, "Retell Create Call")
    retell["parameters"]["bodyParametersJson"] = "{}"
    retell["parameters"]["jsonBody"] = DISPATCH_RETELL_JSON_BODY_EXPR
    return workflow


def _patch_nurture(workflow: Dict[str, Any]) -> Dict[str, Any]:
    fetch = _find_node(workflow, "Fetch Leads")
    fetch["parameters"]["url"] = NURTURE_FETCH_LEADS_URL
    return workflow


def _n8n_headers() -> Dict[str, str]:
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        raise RuntimeError("N8N_API_KEY is required")
    return {"X-N8N-API-KEY": key, "Content-Type": "application/json"}


def _n8n_base() -> str:
    return os.environ.get("N8N_API_BASE", "https://elijah-wallis.app.n8n.cloud/api/v1").rstrip("/")


def _get_remote_workflow(name: str) -> Dict[str, Any]:
    resp = requests.get(f"{_n8n_base()}/workflows", headers=_n8n_headers(), timeout=30)
    resp.raise_for_status()
    rows = resp.json().get("data", [])
    match = next((row for row in rows if row.get("name") == name), None)
    if not match:
        raise RuntimeError(f"workflow not found: {name}")
    wid = match["id"]
    detail = requests.get(f"{_n8n_base()}/workflows/{wid}", headers=_n8n_headers(), timeout=30)
    detail.raise_for_status()
    body = detail.json().get("data", detail.json())
    body["_id"] = wid
    return body


def _update_remote_workflow(detail: Dict[str, Any]) -> None:
    wid = detail["_id"]
    payload = {
        "name": detail.get("name"),
        "nodes": detail.get("nodes"),
        "connections": detail.get("connections"),
        "settings": detail.get("settings") or {},
    }
    resp = requests.put(
        f"{_n8n_base()}/workflows/{wid}",
        headers=_n8n_headers(),
        data=json.dumps(payload),
        timeout=30,
    )
    resp.raise_for_status()


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch campaign filter and cap overrides into n8n workflows.")
    parser.add_argument("--apply-remote", action="store_true")
    args = parser.parse_args()

    dispatch = json.loads(DISPATCH_FILE.read_text(encoding="utf-8"))
    nurture = json.loads(NURTURE_FILE.read_text(encoding="utf-8"))
    dispatch = _patch_dispatch(dispatch)
    nurture = _patch_nurture(nurture)
    _write_json(DISPATCH_FILE, dispatch)
    _write_json(NURTURE_FILE, nurture)

    report: Dict[str, Any] = {"local_files_patched": [str(DISPATCH_FILE), str(NURTURE_FILE)]}
    if args.apply_remote:
        dispatch_remote = _get_remote_workflow("openclaw_retell_call_dispatch")
        nurture_remote = _get_remote_workflow("openclaw_nurture_engine")
        dispatch_remote = _patch_dispatch(dispatch_remote)
        nurture_remote = _patch_nurture(nurture_remote)
        _update_remote_workflow(dispatch_remote)
        _update_remote_workflow(nurture_remote)
        report["remote_updated"] = ["openclaw_retell_call_dispatch", "openclaw_nurture_engine"]
    print(json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
