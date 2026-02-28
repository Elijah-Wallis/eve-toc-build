#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

from n8n_workflow_lifecycle import (
    force_reregister_workflow_webhooks,
    get_workflow_by_name,
    list_webhook_paths,
    n8n_webhook_base,
    verify_webhook_paths_registered,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = ROOT / "workflows_n8n"


def _n8n_base() -> str:
    return os.environ.get("N8N_API_BASE", "https://elijah-wallis.app.n8n.cloud/api/v1").rstrip("/")


def _n8n_headers() -> Dict[str, str]:
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        raise RuntimeError("N8N_API_KEY is required")
    return {"X-N8N-API-KEY": key, "Content-Type": "application/json"}


def _env_expr(name: str, default: str | None = None) -> str:
    if default is None:
        return "={{$env." + name + "}}"
    escaped = default.replace("'", "\\'")
    return "={{$env." + name + " || '" + escaped + "'}}"


def _cfg_node(
    node_id: str,
    position: List[int],
    include_providers: bool = False,
    include_evidence: bool = False,
) -> Dict[str, Any]:
    strings: List[Dict[str, Any]] = [
        {"name": "SUPABASE_URL", "value": _env_expr("SUPABASE_URL")},
        {"name": "SUPABASE_SERVICE_ROLE_KEY", "value": _env_expr("SUPABASE_SERVICE_ROLE_KEY")},
    ]
    if include_providers:
        strings.extend(
            [
                {"name": "N8N_PUBLIC_WEBHOOK_BASE", "value": _env_expr("N8N_PUBLIC_WEBHOOK_BASE", "https://elijah-wallis.app.n8n.cloud")},
                {"name": "APIFY_API_TOKEN", "value": _env_expr("APIFY_API_TOKEN")},
                {"name": "APIFY_ACTOR_ID", "value": _env_expr("APIFY_ACTOR_ID", "compass/crawler-google-places")},
            ]
        )
    if include_evidence:
        strings.extend(
            [
                {"name": "TWILIO_ACCOUNT_SID", "value": _env_expr("TWILIO_ACCOUNT_SID")},
                {"name": "TWILIO_AUTH_TOKEN", "value": _env_expr("TWILIO_AUTH_TOKEN")},
                {"name": "TWILIO_FROM_NUMBER", "value": _env_expr("TWILIO_FROM_NUMBER")},
                {
                    "name": "EVIDENCE_EMAIL_PROVIDER_URL",
                    "value": _env_expr("EVIDENCE_EMAIL_PROVIDER_URL"),
                },
                {
                    "name": "EVIDENCE_EMAIL_API_KEY",
                    "value": _env_expr("EVIDENCE_EMAIL_API_KEY"),
                },
                {
                    "name": "EVIDENCE_EMAIL_FROM",
                    "value": _env_expr("EVIDENCE_EMAIL_FROM", "ops@eve-systems.ai"),
                },
            ]
        )
    return {
        "parameters": {
            "values": {
                "string": strings,
                "number": [
                    {"name": "RATE_LIMIT_LOG_INSIGHT_30M", "value": 6},
                    {"name": "RATE_LIMIT_SET_FOLLOWUP_60M", "value": 4},
                    {"name": "RATE_LIMIT_ENRICH_6H", "value": 3},
                ],
                "boolean": [],
            },
            "options": {},
            "keepOnlySet": False,
        },
        "id": node_id,
        "name": "Config",
        "type": "n8n-nodes-base.set",
        "typeVersion": 2,
        "position": position,
    }


def _webhook_node(node_id: str, name: str, path: str, position: List[int]) -> Dict[str, Any]:
    webhook_id = hashlib.md5(path.encode("utf-8")).hexdigest().upper()  # stable n8n production webhook id
    return {
        "parameters": {
            "path": path,
            "httpMethod": "POST",
            "responseMode": "lastNode",
            "options": {},
        },
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 1,
        "position": position,
        "webhookId": webhook_id,
    }


def _function_node(node_id: str, name: str, code: str, position: List[int]) -> Dict[str, Any]:
    return {
        "parameters": {"functionCode": code},
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.function",
        "typeVersion": 2,
        "position": position,
    }


def _if_bool_node(node_id: str, name: str, value_expr: str, position: List[int]) -> Dict[str, Any]:
    inner = value_expr
    if inner.startswith("={{") and inner.endswith("}}"):
        inner = inner[3:-2]
    elif inner.startswith("={") and inner.endswith("}"):
        inner = inner[2:-1]
    # Coerce boolean into numeric 1/0 for deterministic IF behavior via API.
    value1 = "={{(((" + inner + ") === true || (" + inner + ") === 'true') ? 1 : 0)}}"
    return {
        "parameters": {
            "conditions": {
                "number": [
                    {
                        "value1": value1,
                        "operation": "equal",
                        "value2": 1,
                    }
                ]
            }
        },
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": position,
    }


def _if_number_node(
    node_id: str,
    name: str,
    value_expr: str,
    operation: str,
    value2: float,
    position: List[int],
) -> Dict[str, Any]:
    expr = value_expr
    if expr.startswith("={{") and expr.endswith("}}"):
        expr = "={" + expr[3:-2] + "}"
    return {
        "parameters": {
            "conditions": {
                "number": [
                    {
                        "value1": expr,
                        "operation": operation,
                        "value2": value2,
                    }
                ]
            }
        },
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": position,
    }


def _http_node(
    node_id: str,
    name: str,
    url_expr: str,
    method: str,
    json_body_expr: str,
    position: List[int],
    ) -> Dict[str, Any]:
    return {
        "parameters": {
            "url": url_expr,
            "method": method,
            "jsonParameters": True,
            "options": {},
            "headerParametersJson": "={{JSON.stringify({apikey: $node[\"Config\"].json.SUPABASE_SERVICE_ROLE_KEY, Authorization: \"Bearer \" + $node[\"Config\"].json.SUPABASE_SERVICE_ROLE_KEY, Prefer: \"resolution=merge-duplicates,return=representation\"})}}",
            "sendHeaders": True,
            "specifyHeaders": "json",
            "jsonHeaders": "={{JSON.stringify({apikey: $node[\"Config\"].json.SUPABASE_SERVICE_ROLE_KEY, Authorization: \"Bearer \" + $node[\"Config\"].json.SUPABASE_SERVICE_ROLE_KEY, Prefer: \"resolution=merge-duplicates,return=representation\"})}}",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": json_body_expr,
            "bodyParametersJson": json_body_expr,
        },
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4,
        "position": position,
    }


def _generic_http_node(
    node_id: str,
    name: str,
    url_expr: str,
    method: str,
    position: List[int],
    json_body_expr: str = "{}",
    headers_expr: str = "={{JSON.stringify({})}}",
    send_body: bool = False,
    continue_on_fail: bool = False,
) -> Dict[str, Any]:
    node: Dict[str, Any] = {
        "parameters": {
            "url": url_expr,
            "method": method,
            "jsonParameters": True,
            "options": {"timeout": 120000},
            "headerParametersJson": headers_expr,
            "sendHeaders": True,
            "specifyHeaders": "json",
            "jsonHeaders": headers_expr,
            "sendBody": send_body,
            "specifyBody": "json",
            "jsonBody": json_body_expr,
            "bodyParametersJson": json_body_expr,
        },
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4,
        "position": position,
    }
    if continue_on_fail:
        node["continueOnFail"] = True
    return node


def _supabase_headers_expr() -> str:
    return "={{JSON.stringify({apikey: $node[\"Config\"].json.SUPABASE_SERVICE_ROLE_KEY, Authorization: 'Bearer ' + $node[\"Config\"].json.SUPABASE_SERVICE_ROLE_KEY})}}"


def _workflow_context_brief() -> Dict[str, Any]:
    code = (
        "const req = items[0]?.json || {};\n"
        "const a = (req.body && typeof req.body === 'object') ? req.body : req;\n"
        "const business = a.business_name || a.lead_business_name || 'your practice';\n"
        "const city = a.city || a.lead_city || '';\n"
        "const state = a.state || a.lead_state || '';\n"
        "const rating = a.rating ?? a.lead_rating ?? null;\n"
        "const reviews = a.reviews_count ?? a.lead_reviews_count ?? null;\n"
        "const touch = Number(a.touch_count || 0);\n"
        "const segment = a.segment || a.last_outcome || 'UNKNOWN';\n"
        "const website = a.website || '';\n"
        "const location = [city, state].filter(Boolean).join(', ');\n"
        "const trustLine = rating && reviews ? `${rating}/5 from ${reviews} reviews` : 'local reputation improving';\n"
        "const opener = `Hi, this is Cassidy with an operations audit for ${business}${location ? ' in ' + location : ''}.`;\n"
        "const value_prop = `We help medspas improve lead-speed-to-call and conversion. Current profile suggests ${trustLine}.`;\n"
        "const discovery_questions = [\n"
        "  'How quickly are inbound leads called back right now?',\n"
        "  'Who owns first response during peak hours?',\n"
        "  'Do you track no-show recovery and reactivation?'\n"
        "];\n"
        "const risk_flags = [];\n"
        "if (!website) risk_flags.push('No website captured');\n"
        "if (touch >= 4) risk_flags.push('High touch count; use short CTA');\n"
        "if (segment === 'GATEKEEPER') risk_flags.push('Gatekeeper friction observed');\n"
        "return [{json:{status:'ok',opener,value_prop,discovery_questions,risk_flags,segment,touch_count:touch}}];"
    )
    return {
        "name": "openclaw_retell_fn_context_brief",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-retell-fn-context-brief", [20, 20]),
            _function_node("2", "Build Context Brief", code, [260, 20]),
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Build Context Brief", "type": "main", "index": 0}]]}
        },
        "settings": {},
    }


def _workflow_offer_angle() -> Dict[str, Any]:
    code = (
        "const req = items[0]?.json || {};\n"
        "const a = (req.body && typeof req.body === 'object') ? req.body : req;\n"
        "const rating = Number(a.rating || 0);\n"
        "const reviews = Number(a.reviews_count || 0);\n"
        "const touch = Number(a.touch_count || 0);\n"
        "const positive = !!a.positive_signal;\n"
        "let angle = 'speed_to_lead';\n"
        "if (positive && touch <= 2) angle = 'capacity_expansion';\n"
        "else if (rating > 4.6 && reviews > 120) angle = 'premium_conversion';\n"
        "else if (touch >= 4) angle = 'reactivation';\n"
        "const script = {\n"
        "  speed_to_lead: 'If a lead waits more than a minute, intent decays fast. We can close that gap.',\n"
        "  capacity_expansion: 'You already have demand. We focus on routing and follow-up to unlock more booked consults.',\n"
        "  premium_conversion: 'Strong reputation deserves premium conversion scripts and tighter callback SLAs.',\n"
        "  reactivation: 'We can recover stalled inquiries with a structured 4:1 value-to-ask sequence.'\n"
        "}[angle];\n"
        "return [{json:{status:'ok',angle,script}}];"
    )
    return {
        "name": "openclaw_retell_fn_offer_angle",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-retell-fn-offer-angle", [20, 20]),
            _function_node("2", "Build Offer Angle", code, [260, 20]),
        ],
        "connections": {"Webhook Trigger": {"main": [[{"node": "Build Offer Angle", "type": "main", "index": 0}]]}},
        "settings": {},
    }


def _workflow_log_insight() -> Dict[str, Any]:
    prep = (
        "const req = items[0]?.json || {};\n"
        "const a = (req.body && typeof req.body === 'object') ? req.body : req;\n"
        "if (!a.lead_id) {\n"
        "  return [{json:{guardrail_ok:false,reason_code:'missing_lead_id',reason_detail:'lead_id is required'}}];\n"
        "}\n"
        "if (!a.notes && !a.outcome && !a.next_step && !a.objection) {\n"
        "  return [{json:{guardrail_ok:false,reason_code:'missing_signal_payload',reason_detail:'Provide at least notes, outcome, next_step, or objection'}}];\n"
        "}\n"
        "const now = new Date().toISOString();\n"
        "const eventType = a.event_type || 'retell_call_insight';\n"
        "const idem = a.idempotency_key || `${a.call_id || a.lead_id || a.phone || 'unknown'}-${eventType}-${now}`;\n"
        "const outcome = a.outcome || null;\n"
        "if (outcome && !['GRANTED','STALLED','REVOKED','VOICEMAIL','GATEKEEPER'].includes(String(outcome).toUpperCase())) {\n"
        "  return [{json:{guardrail_ok:false,reason_code:'invalid_outcome',reason_detail:'outcome must be one of GRANTED/STALLED/REVOKED/VOICEMAIL/GATEKEEPER'}}];\n"
        "}\n"
        "const payload = {\n"
        "  call_id: a.call_id || null,\n"
        "  business_name: a.business_name || null,\n"
        "  phone: a.phone || null,\n"
        "  outcome,\n"
        "  objection: a.objection || null,\n"
        "  dm_name: a.dm_name || null,\n"
        "  dm_email: a.dm_email || null,\n"
        "  notes: a.notes || null,\n"
        "  next_step: a.next_step || null,\n"
        "  source: 'retell_tool'\n"
        "};\n"
        "const rateWindowStart = new Date(Date.now() - 30*60*1000).toISOString();\n"
        "return [{json:{guardrail_ok:true,lead_id:a.lead_id||null,place_id:a.place_id||null,event_type:eventType,idempotency_key:idem,payload_json:payload,rate_window_start:rateWindowStart}}];"
    )
    reject_invalid = (
        "return [{json:{status:'rejected',ok:false,reason_code:$json.reason_code || 'invalid_payload',"
        "reason_detail:$json.reason_detail || 'guardrail_reject'}}];"
    )
    reject_rate = (
        "const limit = Number($node[\"Config\"].json.RATE_LIMIT_LOG_INSIGHT_30M || 6);\n"
        "return [{json:{status:'rejected',ok:false,reason_code:'rate_limited_log_insight',reason_detail:`Exceeded ${limit} writes in 30m window`}}];"
    )
    ack = "return [{json:{status:'logged',ok:true,event:items[0]?.json||{}}}];"
    return {
        "name": "openclaw_retell_fn_log_insight",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-retell-fn-log-insight", [20, 20]),
            _cfg_node("2", [220, 20]),
            _function_node("3", "Prepare Insight Event", prep, [440, 20]),
            _if_bool_node("4", "Guardrail OK?", "={{$json.guardrail_ok}}", [660, 20]),
            _function_node("5", "Reject Invalid", reject_invalid, [880, -80]),
            _generic_http_node(
                "6",
                "Fetch Recent Insight Count",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?select=count&lead_id=eq.{{$node[\"Prepare Insight Event\"].json.lead_id}}&event_type=eq.retell_call_insight&created_at=gte.{{$node[\"Prepare Insight Event\"].json.rate_window_start}}",
                "GET",
                [880, 20],
                headers_expr=_supabase_headers_expr(),
                send_body=False,
            ),
            _if_number_node(
                "7",
                "Rate Limited?",
                "={{Number($json.count || 0)}}",
                "largerEqual",
                6,
                [1100, 20],
            ),
            _function_node("8", "Reject Rate Limit", reject_rate, [1320, -80]),
            _http_node(
                "9",
                "Insert Lead Event",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?on_conflict=idempotency_key",
                "POST",
                "={{JSON.stringify({lead_id:$node[\"Prepare Insight Event\"].json.lead_id,place_id:$node[\"Prepare Insight Event\"].json.place_id,event_type:$node[\"Prepare Insight Event\"].json.event_type,idempotency_key:$node[\"Prepare Insight Event\"].json.idempotency_key,payload_json:$node[\"Prepare Insight Event\"].json.payload_json})}}",
                [1320, 20],
            ),
            _function_node("10", "Acknowledge", ack, [1540, 20]),
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Config", "type": "main", "index": 0}]]},
            "Config": {"main": [[{"node": "Prepare Insight Event", "type": "main", "index": 0}]]},
            "Prepare Insight Event": {"main": [[{"node": "Guardrail OK?", "type": "main", "index": 0}]]},
            "Guardrail OK?": {
                "main": [
                    [{"node": "Fetch Recent Insight Count", "type": "main", "index": 0}],
                    [{"node": "Reject Invalid", "type": "main", "index": 0}],
                ]
            },
            "Fetch Recent Insight Count": {"main": [[{"node": "Rate Limited?", "type": "main", "index": 0}]]},
            "Rate Limited?": {
                "main": [
                    [{"node": "Insert Lead Event", "type": "main", "index": 0}],
                    [{"node": "Reject Rate Limit", "type": "main", "index": 0}],
                ]
            },
            "Insert Lead Event": {"main": [[{"node": "Acknowledge", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _workflow_set_followup() -> Dict[str, Any]:
    prep = (
        "const req = items[0]?.json || {};\n"
        "const a = (req.body && typeof req.body === 'object') ? req.body : req;\n"
        "if (!a.lead_id) {\n"
        "  return [{json:{guardrail_ok:false,reason_code:'missing_lead_id',reason_detail:'lead_id is required'}}];\n"
        "}\n"
        "const allowed = ['NEW','NURTURE','RETRY','HOLD','QUALIFIED'];\n"
        "const next = a.next_touch_at || new Date(Date.now() + 3*24*3600*1000).toISOString();\n"
        "const status = a.status || 'NURTURE';\n"
        "if (!allowed.includes(status)) {\n"
        "  return [{json:{guardrail_ok:false,reason_code:'invalid_status',reason_detail:'status must be NEW/NURTURE/RETRY/HOLD/QUALIFIED'}}];\n"
        "}\n"
        "const body = {next_touch_at: next, status};\n"
        "if (a.dm_email) body.dm_email = a.dm_email;\n"
        "if (typeof a.decision_maker_confirmed === 'boolean') body.decision_maker_confirmed = a.decision_maker_confirmed;\n"
        "if (typeof a.positive_signal === 'boolean') body.positive_signal = a.positive_signal;\n"
        "const now = new Date().toISOString();\n"
        "const rateWindowStart = new Date(Date.now() - 60*60*1000).toISOString();\n"
        "const eventPayload = {status, next_touch_at: next, dm_email: a.dm_email || null, decision_maker_confirmed: a.decision_maker_confirmed, positive_signal: a.positive_signal, source: 'retell_tool'};\n"
        "return [{json:{guardrail_ok:true,lead_id:a.lead_id,phone:a.phone||null,body,event_payload:eventPayload,event_type:'retell_followup_plan',idempotency_key:`${a.lead_id}-retell_followup_plan-${now}`,rate_window_start:rateWindowStart}}];"
    )
    reject_invalid = (
        "return [{json:{status:'rejected',ok:false,reason_code:$json.reason_code || 'invalid_payload',"
        "reason_detail:$json.reason_detail || 'guardrail_reject'}}];"
    )
    reject_rate = (
        "const limit = Number($node[\"Config\"].json.RATE_LIMIT_SET_FOLLOWUP_60M || 4);\n"
        "return [{json:{status:'rejected',ok:false,reason_code:'rate_limited_followup',reason_detail:`Exceeded ${limit} follow-up updates in 60m window`}}];"
    )
    prepare_event = (
        "const src = $node[\"Prepare Update\"].json;\n"
        "return [{json:{lead_id:src.lead_id,place_id:null,event_type:src.event_type,idempotency_key:src.idempotency_key,payload_json:src.event_payload}}];"
    )
    ack = "return [{json:{status:'updated',ok:true,result:$json}}];"
    return {
        "name": "openclaw_retell_fn_set_followup",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-retell-fn-set-followup", [20, 20]),
            _cfg_node("2", [220, 20]),
            _function_node("3", "Prepare Update", prep, [440, 20]),
            _if_bool_node("4", "Guardrail OK?", "={{$json.guardrail_ok}}", [660, 20]),
            _function_node("5", "Reject Invalid", reject_invalid, [880, -80]),
            _generic_http_node(
                "6",
                "Fetch Recent Followup Count",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?select=count&lead_id=eq.{{$node[\"Prepare Update\"].json.lead_id}}&event_type=eq.retell_followup_plan&created_at=gte.{{$node[\"Prepare Update\"].json.rate_window_start}}",
                "GET",
                [880, 20],
                headers_expr=_supabase_headers_expr(),
                send_body=False,
            ),
            _if_number_node(
                "7",
                "Rate Limited?",
                "={{Number($json.count || 0)}}",
                "largerEqual",
                4,
                [1100, 20],
            ),
            _function_node("8", "Reject Rate Limit", reject_rate, [1320, -80]),
            _http_node(
                "9",
                "Patch Lead",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/leads?id=eq.{{$node[\"Prepare Update\"].json.lead_id}}",
                "PATCH",
                "={{JSON.stringify($node[\"Prepare Update\"].json.body)}}",
                [1320, 20],
            ),
            _function_node("10", "Prepare Followup Event", prepare_event, [1540, 20]),
            _http_node(
                "11",
                "Insert Followup Event",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?on_conflict=idempotency_key",
                "POST",
                "={{JSON.stringify($json)}}",
                [1760, 20],
            ),
            _function_node("12", "Acknowledge", ack, [1980, 20]),
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Config", "type": "main", "index": 0}]]},
            "Config": {"main": [[{"node": "Prepare Update", "type": "main", "index": 0}]]},
            "Prepare Update": {"main": [[{"node": "Guardrail OK?", "type": "main", "index": 0}]]},
            "Guardrail OK?": {
                "main": [
                    [{"node": "Fetch Recent Followup Count", "type": "main", "index": 0}],
                    [{"node": "Reject Invalid", "type": "main", "index": 0}],
                ]
            },
            "Fetch Recent Followup Count": {"main": [[{"node": "Rate Limited?", "type": "main", "index": 0}]]},
            "Rate Limited?": {
                "main": [
                    [{"node": "Patch Lead", "type": "main", "index": 0}],
                    [{"node": "Reject Rate Limit", "type": "main", "index": 0}],
                ]
            },
            "Patch Lead": {"main": [[{"node": "Prepare Followup Event", "type": "main", "index": 0}]]},
            "Prepare Followup Event": {"main": [[{"node": "Insert Followup Event", "type": "main", "index": 0}]]},
            "Insert Followup Event": {"main": [[{"node": "Acknowledge", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _workflow_send_evidence_package() -> Dict[str, Any]:
    normalize = (
        "const req = items[0]?.json || {};\n"
        "const a = (req.body && typeof req.body === 'object') ? req.body : req;\n"
        "const recipientEmail = String(a.recipient_email || '').trim().toLowerCase();\n"
        "const emailOk = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(recipientEmail);\n"
        "if (!emailOk) {\n"
        "  return [{json:{guardrail_ok:false,reason_code:'invalid_recipient_email',reason_detail:'recipient_email must be valid'}}];\n"
        "}\n"
        "const deliveryMethod = String(a.delivery_method || 'EMAIL_ONLY').trim().toUpperCase();\n"
        "if (!['EMAIL_ONLY','EMAIL_AND_SMS'].includes(deliveryMethod)) {\n"
        "  return [{json:{guardrail_ok:false,reason_code:'invalid_delivery_method',reason_detail:'delivery_method must be EMAIL_ONLY or EMAIL_AND_SMS'}}];\n"
        "}\n"
        "const artifactType = String(a.artifact_type || '').trim().toUpperCase();\n"
        "if (!['AUDIO_LINK','FAILURE_LOG_PDF'].includes(artifactType)) {\n"
        "  return [{json:{guardrail_ok:false,reason_code:'invalid_artifact_type',reason_detail:'artifact_type must be AUDIO_LINK or FAILURE_LOG_PDF'}}];\n"
        "}\n"
        "const evidenceUrl = String(a.evidence_url || a.artifact_url || '').trim();\n"
        "if (!evidenceUrl) {\n"
        "  return [{json:{guardrail_ok:false,reason_code:'missing_artifact_url',reason_detail:'evidence_url is required'}}];\n"
        "}\n"
        "const digits = String(a.phone || '').replace(/\\D/g, '');\n"
        "let phone = null;\n"
        "if (digits.length === 10) phone = '+1' + digits;\n"
        "if (digits.length === 11 && digits[0] === '1') phone = '+' + digits;\n"
        "if (deliveryMethod === 'EMAIL_AND_SMS' && !phone) {\n"
        "  return [{json:{guardrail_ok:false,reason_code:'invalid_phone_for_sms',reason_detail:'phone required for EMAIL_AND_SMS'}}];\n"
        "}\n"
        "const leadId = String(a.lead_id || '').trim() || null;\n"
        "const managerName = String(a.manager_name || '').trim() || 'Practice Manager';\n"
        "const campaignTag = String(a.campaign_tag || '').trim() || null;\n"
        "const subject = String(a.subject_hint || '').trim() || (artifactType === 'AUDIO_LINK' ? 'URGENT: Intake Failure Recording' : 'URGENT: Intake Failure Log');\n"
        "const idemBase = String(a.idempotency_key || '').trim() || `${leadId || recipientEmail}-${artifactType}`;\n"
        "const packageKey = `${idemBase}-pkg`;\n"
        "const rateWindowStart = new Date(Date.now() - 30*60*1000).toISOString();\n"
        "const summaryLine = artifactType === 'AUDIO_LINK' ? 'Missed-call recording attached for review.' : 'Timestamped failure log attached for review.';\n"
        "const smsBody = `EVE alert: ${summaryLine} Link: ${evidenceUrl}`;\n"
        "const emailText = `Hi ${managerName},\\n\\n${summaryLine}\\nArtifact: ${evidenceUrl}\\n\\nPlease confirm receipt and preferred follow-up window.\\n\\n- Eve Systems`;\n"
        "return [{json:{guardrail_ok:true,lead_id:leadId,campaign_tag:campaignTag,recipient_email:recipientEmail,recipient_name:managerName,delivery_method:deliveryMethod,artifact_type:artifactType,evidence_url:evidenceUrl,phone,subject,sms_body:smsBody,email_text:emailText,package_idempotency_key:packageKey,email_event_key:`${idemBase}-email`,sms_event_key:`${idemBase}-sms`,rate_window_start:rateWindowStart,rate_bypass:!leadId}}];"
    )
    reject_invalid = (
        "return [{json:{status:'rejected',ok:false,reason_code:$json.reason_code || 'invalid_payload',reason_detail:$json.reason_detail || 'guardrail_reject'}}];"
    )
    set_rate_zero = "return [{json:{count:0}}];"
    reject_rate = (
        "const limit = Number($node[\"Config\"].json.RATE_LIMIT_SEND_EVIDENCE_30M || 3);\n"
        "return [{json:{status:'rejected',ok:false,reason_code:'rate_limited_send_evidence',reason_detail:`Exceeded ${limit} package requests in 30m`}}];"
    )
    prep_email = (
        "const src = $node['Normalize Request'].json;\n"
        "const cfg = $node['Config'].json;\n"
        "if (!cfg.EVIDENCE_EMAIL_PROVIDER_URL || !cfg.EVIDENCE_EMAIL_API_KEY || !cfg.EVIDENCE_EMAIL_FROM) {\n"
        "  return [{json:{guardrail_ok:false,reason_code:'missing_email_provider_config',reason_detail:'EVIDENCE_EMAIL_PROVIDER_URL/EVIDENCE_EMAIL_API_KEY/EVIDENCE_EMAIL_FROM are required'}}];\n"
        "}\n"
        "return [{json:{guardrail_ok:true,email_body:{to:src.recipient_email,from:cfg.EVIDENCE_EMAIL_FROM,subject:src.subject,text:src.email_text,metadata:{lead_id:src.lead_id,campaign_tag:src.campaign_tag,artifact_type:src.artifact_type,evidence_url:src.evidence_url}}}}];"
    )
    reject_email_cfg = (
        "return [{json:{status:'rejected',ok:false,reason_code:$json.reason_code || 'missing_email_provider_config',reason_detail:$json.reason_detail || 'email provider not configured'}}];"
    )
    prep_email_event = (
        "const src = $node['Normalize Request'].json;\n"
        "const resp = $node['Send Evidence Email'].json || {};\n"
        "const err = String(resp.error || '').trim();\n"
        "const code = Number(resp.statusCode || resp.status || 0) || null;\n"
        "const ok = !err && (!code || (code >= 200 && code < 300));\n"
        "return [{json:{lead_id:src.lead_id,place_id:null,event_type:'retell_evidence_email',idempotency_key:src.email_event_key,payload_json:{ok,status_code:code,error:err || null,recipient_email:src.recipient_email,artifact_type:src.artifact_type,evidence_url:src.evidence_url}}}];"
    )
    prep_sms = (
        "const src = $node['Normalize Request'].json;\n"
        "const sid = String($node['Config'].json.TWILIO_ACCOUNT_SID || '').trim();\n"
        "const token = String($node['Config'].json.TWILIO_AUTH_TOKEN || '').trim();\n"
        "const from = String($node['Config'].json.TWILIO_FROM_NUMBER || '').trim();\n"
        "if (!sid || !token || !from) {\n"
        "  return [{json:{skip:true,reason:'missing_twilio_config'}}];\n"
        "}\n"
        "const auth = Buffer.from(`${sid}:${token}`).toString('base64');\n"
        "return [{json:{skip:false,auth,to:src.phone,from,body:src.sms_body}}];"
    )
    prep_sms_event = (
        "const src = $node['Normalize Request'].json;\n"
        "const prep = $node['Prepare SMS Delivery'].json || {};\n"
        "if (prep.skip) {\n"
        "  return [{json:{lead_id:src.lead_id,place_id:null,event_type:'retell_evidence_sms',idempotency_key:src.sms_event_key,payload_json:{ok:false,skipped:true,reason:prep.reason || 'skipped'}}}];\n"
        "}\n"
        "const resp = $node['Send Evidence SMS'].json || {};\n"
        "const err = String(resp.error || '').trim();\n"
        "const code = Number(resp.statusCode || resp.status || 0) || null;\n"
        "const ok = !err && (!code || (code >= 200 && code < 300));\n"
        "return [{json:{lead_id:src.lead_id,place_id:null,event_type:'retell_evidence_sms',idempotency_key:src.sms_event_key,payload_json:{ok,status_code:code,error:err || null,to:src.phone}}}];"
    )
    prep_package_event = (
        "const src = $node['Normalize Request'].json;\n"
        "const email = ($items('Prepare Email Event', 0, 0)?.[0]?.json || {}).payload_json || {};\n"
        "let sms;\n"
        "if (src.delivery_method === 'EMAIL_ONLY') {\n"
        "  sms = {ok:false,skipped:true,reason:'email_only'};\n"
        "} else {\n"
        "  sms = ($items('Prepare SMS Event', 0, 0)?.[0]?.json || {}).payload_json || {ok:false,skipped:true,reason:'sms_not_recorded'};\n"
        "}\n"
        "const status = (email.ok === true && (sms.ok === true || sms.skipped === true)) ? 'delivered' : 'partial';\n"
        "return [{json:{lead_id:src.lead_id,place_id:null,event_type:'retell_evidence_package',idempotency_key:src.package_idempotency_key,payload_json:{status,email_status:email,sms_status:sms,recipient_email:src.recipient_email,delivery_method:src.delivery_method,artifact_type:src.artifact_type,evidence_url:src.evidence_url}}}];"
    )
    ack = (
        "const pkg = $node['Prepare Package Event'].json || {};\n"
        "const p = pkg.payload_json || {};\n"
        "return [{json:{status:p.status || 'partial',ok:true,email_status:p.email_status || null,sms_status:p.sms_status || null,idempotency_key:pkg.idempotency_key || null}}];"
    )
    return {
        "name": "openclaw_retell_fn_send_evidence_package",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-retell-fn-send-evidence-package", [20, 20]),
            _cfg_node("2", [220, 20], include_evidence=True),
            _function_node("3", "Normalize Request", normalize, [440, 20]),
            _if_bool_node("4", "Guardrail OK?", "={{$json.guardrail_ok}}", [660, 20]),
            _function_node("5", "Reject Invalid", reject_invalid, [880, -120]),
            _if_bool_node("6", "Rate Bypass?", "={{$json.rate_bypass}}", [880, 20]),
            _function_node("7", "Set Rate Count Zero", set_rate_zero, [1100, -80]),
            _generic_http_node(
                "8",
                "Fetch Recent Package Count",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?select=count&lead_id=eq.{{$node[\"Normalize Request\"].json.lead_id}}&event_type=eq.retell_evidence_package&created_at=gte.{{$node[\"Normalize Request\"].json.rate_window_start}}",
                "GET",
                [1100, 120],
                headers_expr=_supabase_headers_expr(),
                send_body=False,
            ),
            _if_number_node("9", "Rate Limited?", "={{Number($json.count || 0)}}", "largerEqual", 3, [1320, 20]),
            _function_node("10", "Reject Rate Limit", reject_rate, [1540, -120]),
            _function_node("11", "Prepare Email Delivery", prep_email, [1540, 80]),
            _if_bool_node("12", "Email Config OK?", "={{$json.guardrail_ok}}", [1760, 80]),
            _function_node("13", "Reject Email Config", reject_email_cfg, [1980, -80]),
            _generic_http_node(
                "14",
                "Send Evidence Email",
                "={{$node[\"Config\"].json.EVIDENCE_EMAIL_PROVIDER_URL}}",
                "POST",
                [1980, 120],
                json_body_expr="={{JSON.stringify($node[\"Prepare Email Delivery\"].json.email_body)}}",
                headers_expr="={{JSON.stringify({Authorization: 'Bearer ' + $node[\"Config\"].json.EVIDENCE_EMAIL_API_KEY, 'Content-Type': 'application/json'})}}",
                send_body=True,
                continue_on_fail=True,
            ),
            _function_node("15", "Prepare Email Event", prep_email_event, [2200, 120]),
            _http_node(
                "16",
                "Insert Email Event",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?on_conflict=idempotency_key",
                "POST",
                "={{JSON.stringify($json)}}",
                [2420, 120],
            ),
            _if_bool_node("17", "Should Send SMS?", "={{$node[\"Normalize Request\"].json.delivery_method === 'EMAIL_AND_SMS'}}", [2640, 120]),
            _function_node("18", "Prepare SMS Delivery", prep_sms, [2860, 40]),
            {
                "parameters": {
                    "url": "=https://api.twilio.com/2010-04-01/Accounts/{{$node[\"Config\"].json.TWILIO_ACCOUNT_SID}}/Messages.json",
                    "method": "POST",
                    "jsonParameters": False,
                    "options": {"timeout": 120000},
                    "bodyParametersUi": {
                        "parameter": [
                            {"name": "To", "value": "={{$json.to}}"},
                            {"name": "From", "value": "={{$json.from}}"},
                            {"name": "Body", "value": "={{$json.body}}"},
                        ]
                    },
                    "headerParametersJson": "={{JSON.stringify({Authorization: `Basic ${$json.auth}`})}}",
                },
                "id": "19",
                "name": "Send Evidence SMS",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4,
                "position": [3080, 40],
                "continueOnFail": True,
            },
            _function_node("20", "Prepare SMS Event", prep_sms_event, [3300, 40]),
            _http_node(
                "21",
                "Insert SMS Event",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?on_conflict=idempotency_key",
                "POST",
                "={{JSON.stringify($json)}}",
                [3520, 40],
            ),
            _function_node("22", "Prepare Package Event", prep_package_event, [3300, 200]),
            _http_node(
                "23",
                "Insert Package Event",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?on_conflict=idempotency_key",
                "POST",
                "={{JSON.stringify($json)}}",
                [3520, 200],
            ),
            _function_node("24", "Acknowledge", ack, [3740, 200]),
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Config", "type": "main", "index": 0}]]},
            "Config": {"main": [[{"node": "Normalize Request", "type": "main", "index": 0}]]},
            "Normalize Request": {"main": [[{"node": "Guardrail OK?", "type": "main", "index": 0}]]},
            "Guardrail OK?": {
                "main": [
                    [{"node": "Rate Bypass?", "type": "main", "index": 0}],
                    [{"node": "Reject Invalid", "type": "main", "index": 0}],
                ]
            },
            "Rate Bypass?": {
                "main": [
                    [{"node": "Set Rate Count Zero", "type": "main", "index": 0}],
                    [{"node": "Fetch Recent Package Count", "type": "main", "index": 0}],
                ]
            },
            "Set Rate Count Zero": {"main": [[{"node": "Rate Limited?", "type": "main", "index": 0}]]},
            "Fetch Recent Package Count": {"main": [[{"node": "Rate Limited?", "type": "main", "index": 0}]]},
            "Rate Limited?": {
                "main": [
                    [{"node": "Prepare Email Delivery", "type": "main", "index": 0}],
                    [{"node": "Reject Rate Limit", "type": "main", "index": 0}],
                ]
            },
            "Prepare Email Delivery": {"main": [[{"node": "Email Config OK?", "type": "main", "index": 0}]]},
            "Email Config OK?": {
                "main": [
                    [{"node": "Send Evidence Email", "type": "main", "index": 0}],
                    [{"node": "Reject Email Config", "type": "main", "index": 0}],
                ]
            },
            "Send Evidence Email": {"main": [[{"node": "Prepare Email Event", "type": "main", "index": 0}]]},
            "Prepare Email Event": {"main": [[{"node": "Insert Email Event", "type": "main", "index": 0}]]},
            "Insert Email Event": {"main": [[{"node": "Should Send SMS?", "type": "main", "index": 0}]]},
            "Should Send SMS?": {
                "main": [
                    [{"node": "Prepare SMS Delivery", "type": "main", "index": 0}],
                    [{"node": "Prepare Package Event", "type": "main", "index": 0}],
                ]
            },
            "Prepare SMS Delivery": {"main": [[{"node": "Send Evidence SMS", "type": "main", "index": 0}]]},
            "Send Evidence SMS": {"main": [[{"node": "Prepare SMS Event", "type": "main", "index": 0}]]},
            "Prepare SMS Event": {"main": [[{"node": "Insert SMS Event", "type": "main", "index": 0}]]},
            "Insert SMS Event": {"main": [[{"node": "Prepare Package Event", "type": "main", "index": 0}]]},
            "Prepare Package Event": {"main": [[{"node": "Insert Package Event", "type": "main", "index": 0}]]},
            "Insert Package Event": {"main": [[{"node": "Acknowledge", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _workflow_mark_dnc() -> Dict[str, Any]:
    prep = (
        "const req = items[0]?.json || {};\n"
        "const a = (req.body && typeof req.body === 'object') ? req.body : req;\n"
        "const digits = String(a.phone || '').replace(/\\D/g, '');\n"
        "let phone = null;\n"
        "if (digits.length === 10) phone = '+1' + digits;\n"
        "if (digits.length === 11 && digits[0] === '1') phone = '+' + digits;\n"
        "if (!phone) {\n"
        "  return [{json:{guardrail_ok:false,reason_code:'invalid_phone',reason_detail:'valid US phone is required'}}];\n"
        "}\n"
        "return [{json:{guardrail_ok:true,phone,reason:a.reason || 'user_request',source:'retell_tool',lead_id:a.lead_id || null,idempotency_key:`${phone}-retell_dnc`}}];"
    )
    reject_invalid = (
        "return [{json:{status:'rejected',ok:false,reason_code:$json.reason_code || 'invalid_payload',"
        "reason_detail:$json.reason_detail || 'guardrail_reject'}}];"
    )
    skip_upsert = "return [{json:{status:'ok',already_dnc:true}}];"
    prep_event = (
        "const src = $node[\"Normalize Phone\"].json;\n"
        "return [{json:{lead_id:src.lead_id || null,place_id:null,event_type:'retell_dnc',idempotency_key:src.idempotency_key,payload_json:{phone:src.phone,reason:src.reason,source:'retell_tool'}}}];"
    )
    ack = "return [{json:{status:'blocked',ok:true,phone:$node[\"Normalize Phone\"].json.phone}}];"
    return {
        "name": "openclaw_retell_fn_mark_dnc",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-retell-fn-mark-dnc", [20, 20]),
            _cfg_node("2", [220, 20]),
            _function_node("3", "Normalize Phone", prep, [440, 20]),
            _if_bool_node("4", "Guardrail OK?", "={{$json.guardrail_ok}}", [660, 20]),
            _function_node("5", "Reject Invalid", reject_invalid, [880, -80]),
            _generic_http_node(
                "6",
                "Check Existing Stoplist",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/stoplist?select=count&phone=eq.{{$node[\"Normalize Phone\"].json.phone}}",
                "GET",
                [880, 20],
                headers_expr=_supabase_headers_expr(),
                send_body=False,
            ),
            _if_number_node(
                "7",
                "Already DNC?",
                "={{Number($json.count || 0)}}",
                "largerEqual",
                1,
                [1100, 20],
            ),
            _function_node("8", "Skip Stoplist Upsert", skip_upsert, [1320, -80]),
            _http_node(
                "9",
                "Upsert Stoplist",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/stoplist?on_conflict=phone",
                "POST",
                "={{JSON.stringify({phone:$node[\"Normalize Phone\"].json.phone,reason:$node[\"Normalize Phone\"].json.reason,source:'retell_tool'})}}",
                [1320, 20],
            ),
            _function_node("10", "Prepare DNC Event", prep_event, [1540, 20]),
            _http_node(
                "11",
                "Insert DNC Event",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?on_conflict=idempotency_key",
                "POST",
                "={{JSON.stringify($json)}}",
                [1760, 20],
            ),
            _function_node("12", "Acknowledge", ack, [1980, 20]),
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Config", "type": "main", "index": 0}]]},
            "Config": {"main": [[{"node": "Normalize Phone", "type": "main", "index": 0}]]},
            "Normalize Phone": {"main": [[{"node": "Guardrail OK?", "type": "main", "index": 0}]]},
            "Guardrail OK?": {
                "main": [
                    [{"node": "Check Existing Stoplist", "type": "main", "index": 0}],
                    [{"node": "Reject Invalid", "type": "main", "index": 0}],
                ]
            },
            "Check Existing Stoplist": {"main": [[{"node": "Already DNC?", "type": "main", "index": 0}]]},
            "Already DNC?": {
                "main": [
                    [{"node": "Skip Stoplist Upsert", "type": "main", "index": 0}],
                    [{"node": "Upsert Stoplist", "type": "main", "index": 0}],
                ]
            },
            "Skip Stoplist Upsert": {"main": [[{"node": "Prepare DNC Event", "type": "main", "index": 0}]]},
            "Upsert Stoplist": {"main": [[{"node": "Prepare DNC Event", "type": "main", "index": 0}]]},
            "Prepare DNC Event": {"main": [[{"node": "Insert DNC Event", "type": "main", "index": 0}]]},
            "Insert DNC Event": {"main": [[{"node": "Acknowledge", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _workflow_enrich_intel() -> Dict[str, Any]:
    prep = (
        "const req = items[0]?.json || {};\n"
        "const a = (req.body && typeof req.body === 'object') ? req.body : req;\n"
        "if (!a.lead_id) {\n"
        "  return [{json:{guardrail_ok:false,reason_code:'missing_lead_id',reason_detail:'lead_id is required for enrichment'}}];\n"
        "}\n"
        "const business = String(a.business_name || '').trim();\n"
        "const city = String(a.city || '').trim();\n"
        "const state = String(a.state || '').trim();\n"
        "const website = String(a.website || '').trim();\n"
        "const email = String(a.email || '').trim();\n"
        "const query = [business, city, state].filter(Boolean).join(' ').trim();\n"
        "if (!query && !website && !email) {\n"
        "  return [{json:{guardrail_ok:false,reason_code:'missing_enrichment_inputs',reason_detail:'provide business_name/city/state or website/email'}}];\n"
        "}\n"
        "const rateWindowStart = new Date(Date.now() - 6*3600*1000).toISOString();\n"
        "return [{json:{guardrail_ok:true,lead_id:a.lead_id,business_name:business,city,state,website,email,search_query:query,rate_window_start:rateWindowStart}}];"
    )
    reject_invalid = (
        "return [{json:{status:'rejected',ok:false,reason_code:$json.reason_code || 'invalid_payload',"
        "reason_detail:$json.reason_detail || 'guardrail_reject'}}];"
    )
    reject_rate = (
        "const limit = Number($node[\"Config\"].json.RATE_LIMIT_ENRICH_6H || 3);\n"
        "return [{json:{status:'rejected',ok:false,reason_code:'rate_limited_enrichment',reason_detail:`Exceeded ${limit} enrich requests in 6h window`}}];"
    )
    build = (
        "const base = ($items('Fetch Lead Snapshot', 0, 0)?.[0]?.json) || null;\n"
        "const apify = $node['Trigger Apify Enrichment'].json || {};\n"
        "const req = $node['Normalize Enrichment Request'].json;\n"
        "const summary = {\n"
        "  status: 'ok',\n"
        "  lead_id: req.lead_id,\n"
        "  profile: {\n"
        "    business_name: req.business_name || base?.business_name || '',\n"
        "    city: req.city || base?.city || '',\n"
        "    state: req.state || base?.state || '',\n"
        "    website: req.website || base?.website || '',\n"
        "    rating: base?.rating ?? null,\n"
        "    reviews_count: base?.reviews_count ?? null,\n"
        "    categories: base?.categories || []\n"
        "  },\n"
        "  providers: {\n"
        "    apify: {triggered: true, response: apify},\n"
        "    supabase: {configured: true, response: base}\n"
        "  },\n"
        "  intel: {\n"
        "    demand_signal: (base?.reviews_count || 0) >= 50 ? 'strong' : 'developing',\n"
        "    trust_signal: (base?.rating || 0) >= 4.5 ? 'high' : 'normal',\n"
        "    recommended_focus: (base?.rating || 0) >= 4.6 ? 'premium_conversion' : 'speed_to_lead'\n"
        "  }\n"
        "};\n"
        "return [{json:summary}];"
    )
    prep_event = (
        "const req = $node['Normalize Enrichment Request'].json;\n"
        "const body = $node['Build Enrichment Response'].json;\n"
        "const now = new Date().toISOString();\n"
        "return [{json:{lead_id:req.lead_id,place_id:null,event_type:'retell_enrichment',idempotency_key:`${req.lead_id}-retell_enrichment-${now}`,payload_json:body}}];"
    )
    ack = "return [{json:{...$node['Build Enrichment Response'].json,logged:true}}];"
    return {
        "name": "openclaw_retell_fn_enrich_intel",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-retell-fn-enrich-intel", [20, 20]),
            _cfg_node("2", [220, 20], include_providers=True),
            _function_node("3", "Normalize Enrichment Request", prep, [440, 20]),
            _if_bool_node("4", "Guardrail OK?", "={{$json.guardrail_ok}}", [660, 20]),
            _function_node("5", "Reject Invalid", reject_invalid, [880, -80]),
            _generic_http_node(
                "6",
                "Fetch Recent Enrichment Count",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?select=count&lead_id=eq.{{$node[\"Normalize Enrichment Request\"].json.lead_id}}&event_type=eq.retell_enrichment&created_at=gte.{{$node[\"Normalize Enrichment Request\"].json.rate_window_start}}",
                "GET",
                [880, 20],
                headers_expr=_supabase_headers_expr(),
                send_body=False,
            ),
            _if_number_node("7", "Rate Limited?", "={{Number($json.count || 0)}}", "largerEqual", 3, [1100, 20]),
            _function_node("8", "Reject Rate Limit", reject_rate, [1320, -80]),
            _generic_http_node(
                "9",
                "Trigger Apify Enrichment",
                "={{($node[\"Config\"].json.N8N_PUBLIC_WEBHOOK_BASE || 'https://elijah-wallis.app.n8n.cloud') + '/webhook/openclaw-apify-ingest'}}",
                "POST",
                [1320, 20],
                json_body_expr="={{JSON.stringify({searchStringsArray:[($node[\"Normalize Enrichment Request\"].json.search_query || '')], apify_input:{includeWebResults:false,language:'en',maxCrawledPlacesPerSearch:1,maxImages:0,maximumLeadsEnrichmentRecords:0,scrapeContacts:false,scrapeDirectories:false,scrapeImageAuthors:false,scrapePlaceDetailPage:false,scrapeReviewsPersonalData:true,scrapeSocialMediaProfiles:{facebooks:false,instagrams:false,tiktoks:false,twitters:false,youtubes:false},scrapeTableReservationProvider:false,searchStringsArray:[($node[\"Normalize Enrichment Request\"].json.search_query || '')],skipClosedPlaces:true}})}}",
                headers_expr="={{JSON.stringify({'Content-Type':'application/json'})}}",
                send_body=True,
                continue_on_fail=True,
            ),
            _generic_http_node(
                "10",
                "Fetch Lead Snapshot",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/leads?select=id,business_name,city,state,website,rating,reviews_count,categories,status,touch_count&id=eq.{{$node[\"Normalize Enrichment Request\"].json.lead_id}}&limit=1",
                "GET",
                [1540, 20],
                headers_expr="={{JSON.stringify({apikey: $node[\"Config\"].json.SUPABASE_SERVICE_ROLE_KEY, Authorization: 'Bearer ' + $node[\"Config\"].json.SUPABASE_SERVICE_ROLE_KEY})}}",
                send_body=False,
                continue_on_fail=True,
            ),
            _function_node("13", "Build Enrichment Response", build, [1760, 20]),
            _function_node("14", "Prepare Enrichment Event", prep_event, [1980, 20]),
            _http_node(
                "15",
                "Insert Enrichment Event",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?on_conflict=idempotency_key",
                "POST",
                "={{JSON.stringify($json)}}",
                [2200, 20],
            ),
            _function_node("16", "Acknowledge", ack, [2420, 20]),
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Config", "type": "main", "index": 0}]]},
            "Config": {"main": [[{"node": "Normalize Enrichment Request", "type": "main", "index": 0}]]},
            "Normalize Enrichment Request": {"main": [[{"node": "Guardrail OK?", "type": "main", "index": 0}]]},
            "Guardrail OK?": {
                "main": [
                    [{"node": "Fetch Recent Enrichment Count", "type": "main", "index": 0}],
                    [{"node": "Reject Invalid", "type": "main", "index": 0}],
                ]
            },
            "Fetch Recent Enrichment Count": {"main": [[{"node": "Rate Limited?", "type": "main", "index": 0}]]},
            "Rate Limited?": {
                "main": [
                    [{"node": "Reject Rate Limit", "type": "main", "index": 0}],
                    [{"node": "Trigger Apify Enrichment", "type": "main", "index": 0}],
                ]
            },
            "Trigger Apify Enrichment": {"main": [[{"node": "Fetch Lead Snapshot", "type": "main", "index": 0}]]},
            "Fetch Lead Snapshot": {"main": [[{"node": "Build Enrichment Response", "type": "main", "index": 0}]]},
            "Build Enrichment Response": {"main": [[{"node": "Prepare Enrichment Event", "type": "main", "index": 0}]]},
            "Prepare Enrichment Event": {"main": [[{"node": "Insert Enrichment Event", "type": "main", "index": 0}]]},
            "Insert Enrichment Event": {"main": [[{"node": "Acknowledge", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _workflow_feedback_nightly() -> Dict[str, Any]:
    build = (
        "const rows = items.map(i => i.json || {}).filter(r => r.lead_id);\n"
        "if (!rows.length) return [{json:{status:'no_updates',segments:[],events:[],lead_count:0}}];\n"
        "const scoreMap = {GRANTED:3, STALLED:1, VOICEMAIL:-1, GATEKEEPER:-1, REVOKED:-3};\n"
        "const grouped = new Map();\n"
        "for (const r of rows) {\n"
        "  const leadId = r.lead_id;\n"
        "  if (!grouped.has(leadId)) grouped.set(leadId, {score:0,latest:r.outcome || 'STALLED'});\n"
        "  const g = grouped.get(leadId);\n"
        "  const o = String(r.outcome || 'STALLED').toUpperCase();\n"
        "  g.score += (scoreMap[o] ?? 0);\n"
        "  if (!g.latest) g.latest = o;\n"
        "}\n"
        "const now = new Date().toISOString();\n"
        "const segments = [];\n"
        "const events = [];\n"
        "for (const [lead_id, g] of grouped.entries()) {\n"
        "  const latest = String(g.latest || 'STALLED').toUpperCase();\n"
        "  const segment = ['GRANTED','STALLED','REVOKED','VOICEMAIL','GATEKEEPER'].includes(latest) ? latest : 'STALLED';\n"
        "  let next_best_action = 'retry_call_time_shift';\n"
        "  if (segment === 'GRANTED') next_best_action = 'handoff_email_and_schedule';\n"
        "  else if (segment === 'STALLED') next_best_action = 'send_value_report_and_retry';\n"
        "  else if (segment === 'GATEKEEPER') next_best_action = 'obtain_direct_ops_contact';\n"
        "  else if (segment === 'VOICEMAIL') next_best_action = 'leave_value_voicemail_and_retry';\n"
        "  else if (segment === 'REVOKED') next_best_action = 'suppress_and_hold';\n"
        "  segments.push({lead_id, segment, last_updated: now});\n"
        "  events.push({lead_id, place_id:null, event_type:'nightly_feedback_loop', idempotency_key:`${lead_id}-nightly_feedback_loop-${now.slice(0,10)}`, payload_json:{score:g.score, latest_outcome:segment, next_best_action, source:'nightly_feedback'}});\n"
        "}\n"
        "return [{json:{status:'ok',segments,events,lead_count:grouped.size}}];"
    )
    no_updates = "return [{json:{status:'no_updates',lead_count:0,segment_updates:0,nba_updates:0}}];"
    ack = (
        "const src = $node['Build Segment+NBA Payloads'].json;\n"
        "return [{json:{status:'ok',lead_count:src.lead_count || 0,segment_updates:(src.segments || []).length,nba_updates:(src.events || []).length}}];"
    )
    return {
        "name": "openclaw_feedback_nightly",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-feedback-nightly", [20, 20]),
            _cfg_node("2", [220, 20]),
            _generic_http_node(
                "3",
                "Fetch Recent Calls",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/call_sessions?select=lead_id,outcome,created_at&lead_id=not.is.null&created_at=gte.{{new Date(Date.now()-((($json.lookback_hours || ($json.body && $json.body.lookback_hours)) || 24) * 3600 * 1000)).toISOString()}}&order=created_at.desc&limit=2000",
                "GET",
                [440, 20],
                headers_expr="={{JSON.stringify({apikey: $node[\"Config\"].json.SUPABASE_SERVICE_ROLE_KEY, Authorization: 'Bearer ' + $node[\"Config\"].json.SUPABASE_SERVICE_ROLE_KEY})}}",
                send_body=False,
            ),
            _function_node("4", "Build Segment+NBA Payloads", build, [660, 20]),
            _if_bool_node("5", "Has Updates?", "={{$json.status === 'ok' && Number($json.lead_count || 0) > 0}}", [880, 20]),
            _function_node("6", "No Updates", no_updates, [1100, -80]),
            _http_node(
                "7",
                "Upsert Segments",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/segments?on_conflict=lead_id",
                "POST",
                "={{JSON.stringify($node[\"Build Segment+NBA Payloads\"].json.segments || [])}}",
                [1100, 20],
            ),
            _http_node(
                "8",
                "Insert NBA Events",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?on_conflict=idempotency_key",
                "POST",
                "={{JSON.stringify($node[\"Build Segment+NBA Payloads\"].json.events || [])}}",
                [1320, 20],
            ),
            _function_node("9", "Acknowledge", ack, [1540, 20]),
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Config", "type": "main", "index": 0}]]},
            "Config": {"main": [[{"node": "Fetch Recent Calls", "type": "main", "index": 0}]]},
            "Fetch Recent Calls": {"main": [[{"node": "Build Segment+NBA Payloads", "type": "main", "index": 0}]]},
            "Build Segment+NBA Payloads": {"main": [[{"node": "Has Updates?", "type": "main", "index": 0}]]},
            "Has Updates?": {
                "main": [
                    [{"node": "Upsert Segments", "type": "main", "index": 0}],
                    [{"node": "No Updates", "type": "main", "index": 0}],
                ]
            },
            "Upsert Segments": {"main": [[{"node": "Insert NBA Events", "type": "main", "index": 0}]]},
            "Insert NBA Events": {"main": [[{"node": "Acknowledge", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _workflows() -> List[Tuple[str, Dict[str, Any]]]:
    return [
        ("openclaw_retell_fn_context_brief.json", _workflow_context_brief()),
        ("openclaw_retell_fn_offer_angle.json", _workflow_offer_angle()),
        ("openclaw_retell_fn_log_insight.json", _workflow_log_insight()),
        ("openclaw_retell_fn_set_followup.json", _workflow_set_followup()),
        ("openclaw_retell_fn_send_evidence_package.json", _workflow_send_evidence_package()),
        ("openclaw_retell_fn_mark_dnc.json", _workflow_mark_dnc()),
        ("openclaw_retell_fn_enrich_intel.json", _workflow_enrich_intel()),
        ("openclaw_feedback_nightly.json", _workflow_feedback_nightly()),
    ]


def _list_remote_workflows() -> List[Dict[str, Any]]:
    resp = requests.get(f"{_n8n_base()}/workflows", headers=_n8n_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def _upsert_remote(workflow: Dict[str, Any]) -> str:
    rows = _list_remote_workflows()
    existing = next((r for r in rows if r.get("name") == workflow["name"]), None)
    payload = {
        "name": workflow["name"],
        "nodes": workflow["nodes"],
        "connections": workflow["connections"],
        "settings": workflow.get("settings", {}),
    }
    if existing:
        wid = existing["id"]
        resp = requests.put(f"{_n8n_base()}/workflows/{wid}", headers=_n8n_headers(), data=json.dumps(payload), timeout=30)
        resp.raise_for_status()
        return f"updated:{wid}"
    resp = requests.post(f"{_n8n_base()}/workflows", headers=_n8n_headers(), data=json.dumps(payload), timeout=30)
    resp.raise_for_status()
    body = resp.json().get("data", resp.json())
    wid = body.get("id") or body.get("workflowId") or "unknown"
    return f"created:{wid}"


def _enable_mcp(name: str) -> str:
    rows = _list_remote_workflows()
    existing = next((r for r in rows if r.get("name") == name), None)
    if not existing:
        return "not_found"
    wid = existing["id"]
    detail = requests.get(f"{_n8n_base()}/workflows/{wid}", headers=_n8n_headers(), timeout=30).json()
    data = detail.get("data", detail)
    settings = dict(data.get("settings") or {})
    settings["availableInMCP"] = True
    payload = {
        "name": data.get("name"),
        "nodes": data.get("nodes"),
        "connections": data.get("connections"),
        "settings": settings,
    }
    resp = requests.put(f"{_n8n_base()}/workflows/{wid}", headers=_n8n_headers(), data=json.dumps(payload), timeout=30)
    if resp.status_code >= 400:
        return f"failed:{resp.status_code}"
    return "ok"


def _activate_workflow(name: str) -> str:
    workflow = get_workflow_by_name(name)
    if not workflow:
        return "not_found"
    workflow_id = str(workflow.get("_id") or workflow.get("id") or "")
    if not workflow_id:
        return "failed:missing_workflow_id"
    try:
        force_reregister_workflow_webhooks(workflow_id)
    except Exception as exc:  # noqa: BLE001
        return f"failed:reregister:{type(exc).__name__}"
    webhook_paths = list_webhook_paths(workflow)
    if not webhook_paths:
        return "ok:no_webhooks"
    probe_payloads = {
        "openclaw-retell-dispatch": {"source_filter": "__probe_noop__", "lead_limit": 0, "max_calls": 0},
        "openclaw-nurture-run": {"source_filter": "__probe_noop__", "lead_limit": 0},
    }
    verify = verify_webhook_paths_registered(
        base_webhook_url=n8n_webhook_base(),
        paths=webhook_paths,
        probe_payloads=probe_payloads,
    )
    if verify.get("status") != "ok":
        return "failed:verify"
    return "ok"


def _upsert_feedback_cron_job() -> str:
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not supabase_key:
        return "skipped:missing_supabase"
    headers = {
        "Content-Type": "application/json",
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }
    payload = {
        "name": "cron:openclaw-feedback-nightly",
        "cron": "5 3 * * *",
        "task_type": "n8n.trigger",
        "payload_json": {"workflow": "openclaw-feedback-nightly", "data": {"lookback_hours": 24}},
        "active": True,
    }
    resp = requests.post(
        f"{supabase_url}/rest/v1/cron_jobs?on_conflict=name",
        headers=headers,
        data=json.dumps(payload),
        timeout=30,
    )
    if resp.status_code >= 400:
        return f"failed:{resp.status_code}"
    return "ok"


def main() -> int:
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {"local_files": [], "remote": {}}
    for filename, wf in _workflows():
        out = WORKFLOWS_DIR / filename
        out.write_text(json.dumps(wf, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        report["local_files"].append(str(out))
        status = _upsert_remote(wf)
        report["remote"][wf["name"]] = status
        report["remote"][f"{wf['name']}:mcp"] = _enable_mcp(wf["name"])
        report["remote"][f"{wf['name']}:active"] = _activate_workflow(wf["name"])
    report["feedback_cron"] = _upsert_feedback_cron_job()
    print(json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
