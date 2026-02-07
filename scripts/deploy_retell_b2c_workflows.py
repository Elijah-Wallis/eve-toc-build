#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


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


def _cfg_node(node_id: str, position: List[int], include_supabase: bool = True, include_retell: bool = False) -> Dict[str, Any]:
    strings: List[Dict[str, Any]] = []
    if include_supabase:
        strings.extend(
            [
                {"name": "SUPABASE_URL", "value": _env_expr("SUPABASE_URL")},
                {"name": "SUPABASE_SERVICE_ROLE_KEY", "value": _env_expr("SUPABASE_SERVICE_ROLE_KEY")},
            ]
        )
    if include_retell:
        strings.extend(
            [
                {"name": "RETELL_AI_KEY", "value": _env_expr("RETELL_AI_KEY")},
                {"name": "RETELL_FROM_NUMBER", "value": _env_expr("RETELL_FROM_NUMBER")},
                {"name": "RETELL_AGENT_B2C_ID", "value": _env_expr("RETELL_AGENT_B2C_ID")},
            ]
        )
    strings.extend(
        [
            {"name": "B2C_CLINIC_NAME", "value": _env_expr("B2C_CLINIC_NAME", "Your MedSpa")},
            {"name": "B2C_TIMEZONE", "value": _env_expr("B2C_TIMEZONE", "America/Chicago")},
            {"name": "B2C_OPEN_HOUR", "value": _env_expr("B2C_OPEN_HOUR", "9")},
            {"name": "B2C_CLOSE_HOUR", "value": _env_expr("B2C_CLOSE_HOUR", "18")},
            {
                "name": "B2C_CREDENTIALS_BLURB",
                "value": _env_expr("B2C_CREDENTIALS_BLURB", "Board-certified clinical team and medical director oversight"),
            },
        ]
    )
    return {
        "parameters": {
            "values": {"string": strings, "number": [], "boolean": []},
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
    webhook_id = hashlib.md5(path.encode("utf-8")).hexdigest().upper()
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
        "parameters": {"conditions": {"number": [{"value1": value1, "operation": "equal", "value2": 1}]}},
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": position,
    }


def _if_number_node(node_id: str, name: str, value_expr: str, operation: str, value2: float, position: List[int]) -> Dict[str, Any]:
    expr = value_expr
    if expr.startswith("={{") and expr.endswith("}}"):
        expr = "={" + expr[3:-2] + "}"
    return {
        "parameters": {
            "conditions": {"number": [{"value1": expr, "operation": operation, "value2": value2}]}
        },
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": position,
    }


def _split_node(node_id: str, name: str, position: List[int]) -> Dict[str, Any]:
    return {
        "parameters": {"batchSize": 1},
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.splitInBatches",
        "typeVersion": 1,
        "position": position,
    }


def _http_node(
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


def _supabase_headers_expr(prefer: str | None = None) -> str:
    if prefer:
        return (
            "={{JSON.stringify({apikey: $node[\"Config\"].json.SUPABASE_SERVICE_ROLE_KEY, "
            "Authorization: 'Bearer ' + $node[\"Config\"].json.SUPABASE_SERVICE_ROLE_KEY, "
            f"Prefer: '{prefer}'}})"
            "}}"
        )
    return (
        "={{JSON.stringify({apikey: $node[\"Config\"].json.SUPABASE_SERVICE_ROLE_KEY, "
        "Authorization: 'Bearer ' + $node[\"Config\"].json.SUPABASE_SERVICE_ROLE_KEY})}}"
    )


def _retell_headers_expr() -> str:
    return "={{JSON.stringify({Authorization: 'Bearer ' + $node[\"Config\"].json.RETELL_AI_KEY})}}"


def _workflow_b2c_context() -> Dict[str, Any]:
    code = (
        "const req = items[0]?.json || {};\n"
        "const a = (req.body && typeof req.body === 'object') ? req.body : req;\n"
        "const clinic = a.clinic_name || $node['Config'].json.B2C_CLINIC_NAME || 'the clinic';\n"
        "const firstName = a.patient_name || a.first_name || 'there';\n"
        "const concern = a.concern || a.service_interest || 'consultation';\n"
        "const urgency = a.urgency || 'standard';\n"
        "const credentials = $node['Config'].json.B2C_CREDENTIALS_BLURB || 'licensed clinical oversight';\n"
        "return [{json:{status:'ok',opening:`Hi ${firstName}, thanks for reaching out to ${clinic}.`,"
        "trust_anchor:`You would be working with a ${credentials}.`,"
        "intent_summary:`Primary concern: ${concern}. Urgency: ${urgency}.`,"
        "next_step:'I can share pricing range, check available times, and book in one flow.'}}];"
    )
    return {
        "name": "openclaw_retell_fn_b2c_context",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-retell-fn-b2c-context", [20, 20]),
            _cfg_node("2", [220, 20], include_supabase=False, include_retell=False),
            _function_node("3", "Build B2C Context", code, [460, 20]),
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Config", "type": "main", "index": 0}]]},
            "Config": {"main": [[{"node": "Build B2C Context", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _workflow_b2c_availability() -> Dict[str, Any]:
    code = (
        "const req = items[0]?.json || {};\n"
        "const a = (req.body && typeof req.body === 'object') ? req.body : req;\n"
        "const tz = a.timezone || $node['Config'].json.B2C_TIMEZONE || 'America/Chicago';\n"
        "const slotMin = Math.max(15, Math.min(60, Number(a.slot_minutes || 30)));\n"
        "const openHour = Number($node['Config'].json.B2C_OPEN_HOUR || 9);\n"
        "const closeHour = Number($node['Config'].json.B2C_CLOSE_HOUR || 18);\n"
        "const slots = [];\n"
        "let probe = new Date(Date.now() + 2 * 3600 * 1000);\n"
        "let guard = 0;\n"
        "while (slots.length < 8 && guard < 600) {\n"
        "  const hourParts = new Intl.DateTimeFormat('en-US', { timeZone: tz, hour: '2-digit', hour12: false }).formatToParts(probe);\n"
        "  const dowParts = new Intl.DateTimeFormat('en-US', { timeZone: tz, weekday: 'short' }).formatToParts(probe);\n"
        "  const hour = Number(hourParts.find(p => p.type === 'hour')?.value || '0');\n"
        "  const day = dowParts.find(p => p.type === 'weekday')?.value || '';\n"
        "  if (day !== 'Sun' && hour >= openHour && hour < closeHour) {\n"
        "    slots.push({slot_iso: probe.toISOString(), timezone: tz});\n"
        "  }\n"
        "  probe = new Date(probe.getTime() + slotMin * 60000);\n"
        "  guard += 1;\n"
        "}\n"
        "return [{json:{status:'ok',timezone:tz,slot_minutes:slotMin,slots}}];"
    )
    return {
        "name": "openclaw_retell_fn_b2c_availability",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-retell-fn-b2c-availability", [20, 20]),
            _cfg_node("2", [220, 20], include_supabase=False, include_retell=False),
            _function_node("3", "Build Availability", code, [460, 20]),
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Config", "type": "main", "index": 0}]]},
            "Config": {"main": [[{"node": "Build Availability", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _workflow_b2c_quote() -> Dict[str, Any]:
    code = (
        "const req = items[0]?.json || {};\n"
        "const a = (req.body && typeof req.body === 'object') ? req.body : req;\n"
        "const service = String(a.service_interest || a.concern || 'consultation').toLowerCase();\n"
        "const ranges = [\n"
        "  {k:'botox', label:'Neurotoxin treatment', min:350, max:900},\n"
        "  {k:'filler', label:'Dermal filler', min:700, max:2400},\n"
        "  {k:'laser', label:'Laser package', min:450, max:1800},\n"
        "  {k:'facial', label:'Medical facial', min:150, max:450},\n"
        "  {k:'body', label:'Body contouring session', min:600, max:3200}\n"
        "];\n"
        "let match = ranges.find(r => service.includes(r.k));\n"
        "if (!match) match = {label:'Consultation-first care plan', min:100, max:350};\n"
        "return [{json:{status:'ok',service_label:match.label,price_range_usd:{min:match.min,max:match.max},"
        "disclaimer:'Final pricing depends on clinician assessment, candidacy, and treatment plan.'}}];"
    )
    return {
        "name": "openclaw_retell_fn_b2c_quote",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-retell-fn-b2c-quote", [20, 20]),
            _function_node("2", "Build Quote Range", code, [260, 20]),
        ],
        "connections": {"Webhook Trigger": {"main": [[{"node": "Build Quote Range", "type": "main", "index": 0}]]}},
        "settings": {},
    }


def _workflow_b2c_book_appointment() -> Dict[str, Any]:
    normalize = (
        "const req = items[0]?.json || {};\n"
        "const a = (req.body && typeof req.body === 'object') ? req.body : req;\n"
        "const leadId = String(a.lead_id || '').trim();\n"
        "const patientName = String(a.patient_name || '').trim();\n"
        "const email = String(a.email || '').trim() || null;\n"
        "const timezone = String(a.timezone || $node['Config'].json.B2C_TIMEZONE || 'America/Chicago').trim();\n"
        "const serviceInterest = String(a.service_interest || '').trim() || null;\n"
        "const appointmentRaw = String(a.appointment_at_iso || a.appointment_time || '').trim();\n"
        "const digits = String(a.phone || '').replace(/\\D/g, '');\n"
        "let phone = null;\n"
        "if (digits.length === 10) phone = '+1' + digits;\n"
        "if (digits.length === 11 && digits[0] === '1') phone = '+' + digits;\n"
        "if (!patientName) return [{json:{guardrail_ok:false,reason_code:'missing_patient_name',reason_detail:'patient_name is required'}}];\n"
        "if (!appointmentRaw) return [{json:{guardrail_ok:false,reason_code:'missing_appointment_time',reason_detail:'appointment_at_iso is required'}}];\n"
        "const appt = new Date(appointmentRaw);\n"
        "if (Number.isNaN(appt.getTime())) return [{json:{guardrail_ok:false,reason_code:'invalid_appointment_time',reason_detail:'appointment_at_iso must be ISO-8601'}}];\n"
        "if (appt.getTime() < Date.now() - 5*60*1000) return [{json:{guardrail_ok:false,reason_code:'appointment_in_past',reason_detail:'appointment time must be in the future'}}];\n"
        "if (!leadId && !phone) return [{json:{guardrail_ok:false,reason_code:'missing_identity',reason_detail:'lead_id or phone is required'}}];\n"
        "const reminder24 = new Date(appt.getTime() - 24 * 3600 * 1000).toISOString();\n"
        "const reminder2 = new Date(appt.getTime() - 2 * 3600 * 1000).toISOString();\n"
        "const idBase = `${leadId || phone}-${appt.toISOString()}`;\n"
        "return [{json:{guardrail_ok:true,lead_id:leadId || null,phone,patient_name:patientName,email,timezone,service_interest:serviceInterest,appointment_at_iso:appt.toISOString(),reminder_24_iso:reminder24,reminder_2_iso:reminder2,id_base:idBase}}];"
    )
    reject = (
        "return [{json:{status:'rejected',ok:false,reason_code:$json.reason_code || 'invalid_payload',reason_detail:$json.reason_detail || 'guardrail_reject'}}];"
    )
    resolve = (
        "const req = $node['Normalize Appointment Request'].json;\n"
        "const raw = $node['Lookup Lead'].json;\n"
        "const row = Array.isArray(raw) ? (raw[0] || null) : (raw && raw.id ? raw : null);\n"
        "const shouldCreate = !row;\n"
        "const createBody = {\n"
        "  source: 'retell.b2c.demo',\n"
        "  place_id: null,\n"
        "  business_name: req.patient_name,\n"
        "  phone: req.phone,\n"
        "  email: req.email,\n"
        "  status: 'NEW',\n"
        "  lead_type: 'B2C',\n"
        "  decision_maker_confirmed: true,\n"
        "  positive_signal: true,\n"
        "  touch_count: 0\n"
        "};\n"
        "return [{json:{...req,resolved_lead:row,should_create:shouldCreate,create_body:createBody}}];"
    )
    finalize = (
        "const src = $node['Resolve Lead'].json;\n"
        "let leadId = src.resolved_lead?.id || null;\n"
        "if (!leadId) {\n"
        "  const created = $node['Create Lead'].json;\n"
        "  const row = Array.isArray(created) ? (created[0] || null) : (created && created.id ? created : null);\n"
        "  leadId = row?.id || null;\n"
        "}\n"
        "if (!leadId) return [{json:{guardrail_ok:false,reason_code:'lead_resolution_failed',reason_detail:'could not resolve or create lead'}}];\n"
        "const reminderEvents = [\n"
        "  {lead_id: leadId, place_id: null, event_type: 'b2c_showrate_reminder', idempotency_key: `${src.id_base}-h24`, payload_json: {window:'H24', remind_at: src.reminder_24_iso, timezone: src.timezone, appointment_at_iso: src.appointment_at_iso}},\n"
        "  {lead_id: leadId, place_id: null, event_type: 'b2c_showrate_reminder', idempotency_key: `${src.id_base}-h2`, payload_json: {window:'H2', remind_at: src.reminder_2_iso, timezone: src.timezone, appointment_at_iso: src.appointment_at_iso}}\n"
        "];\n"
        "return [{json:{guardrail_ok:true,lead_id:leadId,patient_name:src.patient_name,email:src.email,phone:src.phone,timezone:src.timezone,service_interest:src.service_interest,appointment_at_iso:src.appointment_at_iso,id_base:src.id_base,reminder_events:reminderEvents}}];"
    )
    ack = (
        "return [{json:{status:'booked',ok:true,lead_id:$json.lead_id,appointment_at_iso:$json.appointment_at_iso,timezone:$json.timezone,confirmation_text:`Booked ${$json.patient_name} for ${$json.appointment_at_iso} (${ $json.timezone }).`}}];"
    )
    return {
        "name": "openclaw_retell_fn_b2c_book_appointment",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-retell-fn-b2c-book-appointment", [20, 20]),
            _cfg_node("2", [220, 20], include_supabase=True, include_retell=False),
            _function_node("3", "Normalize Appointment Request", normalize, [440, 20]),
            _if_bool_node("4", "Guardrail OK?", "={{$json.guardrail_ok}}", [660, 20]),
            _function_node("5", "Reject Invalid", reject, [880, -80]),
            _http_node(
                "6",
                "Lookup Lead",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/leads?select=id,phone,email,status,lead_type,business_name&limit=1{{$node[\"Normalize Appointment Request\"].json.lead_id ? '&id=eq.' + encodeURIComponent($node[\"Normalize Appointment Request\"].json.lead_id) : '&phone=eq.' + encodeURIComponent($node[\"Normalize Appointment Request\"].json.phone || '')}}",
                "GET",
                [880, 20],
                headers_expr=_supabase_headers_expr(),
                send_body=False,
            ),
            _function_node("7", "Resolve Lead", resolve, [1100, 20]),
            _if_bool_node("8", "Need Create?", "={{$json.should_create}}", [1320, 20]),
            _http_node(
                "9",
                "Create Lead",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/leads",
                "POST",
                [1540, -80],
                json_body_expr="={{JSON.stringify($node[\"Resolve Lead\"].json.create_body)}}",
                headers_expr=_supabase_headers_expr("return=representation"),
                send_body=True,
            ),
            _function_node("10", "Finalize Lead Resolution", finalize, [1540, 80]),
            _if_bool_node("11", "Lead Resolved?", "={{$json.guardrail_ok}}", [1760, 80]),
            _function_node("12", "Reject Unresolved", reject, [1980, -40]),
            _http_node(
                "13",
                "Patch Lead Appointment",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/leads?id=eq.{{$json.lead_id}}",
                "PATCH",
                [1980, 80],
                json_body_expr="={{JSON.stringify({status:'QUALIFIED',lead_type:'B2C',decision_maker_confirmed:true,positive_signal:true,next_touch_at:$json.appointment_at_iso,dm_email:$json.email,last_contacted_at:new Date().toISOString()})}}",
                headers_expr=_supabase_headers_expr("return=minimal"),
                send_body=True,
            ),
            _http_node(
                "14",
                "Insert Appointment Event",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?on_conflict=idempotency_key",
                "POST",
                [2200, 80],
                json_body_expr="={{JSON.stringify({lead_id:$json.lead_id,place_id:null,event_type:'b2c_appointment_booked',idempotency_key:$json.id_base + '-booked',payload_json:{appointment_at_iso:$json.appointment_at_iso,timezone:$json.timezone,service_interest:$json.service_interest,phone:$json.phone,email:$json.email,source:'retell_b2c'}})}}",
                headers_expr=_supabase_headers_expr("resolution=ignore-duplicates,return=minimal"),
                send_body=True,
            ),
            _http_node(
                "15",
                "Insert Reminder Events",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?on_conflict=idempotency_key",
                "POST",
                [2420, 80],
                json_body_expr="={{JSON.stringify($json.reminder_events)}}",
                headers_expr=_supabase_headers_expr("resolution=ignore-duplicates,return=minimal"),
                send_body=True,
            ),
            _function_node("16", "Acknowledge", ack, [2640, 80]),
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Config", "type": "main", "index": 0}]]},
            "Config": {"main": [[{"node": "Normalize Appointment Request", "type": "main", "index": 0}]]},
            "Normalize Appointment Request": {"main": [[{"node": "Guardrail OK?", "type": "main", "index": 0}]]},
            "Guardrail OK?": {
                "main": [
                    [{"node": "Lookup Lead", "type": "main", "index": 0}],
                    [{"node": "Reject Invalid", "type": "main", "index": 0}],
                ]
            },
            "Lookup Lead": {"main": [[{"node": "Resolve Lead", "type": "main", "index": 0}]]},
            "Resolve Lead": {"main": [[{"node": "Need Create?", "type": "main", "index": 0}]]},
            "Need Create?": {
                "main": [
                    [{"node": "Create Lead", "type": "main", "index": 0}],
                    [{"node": "Finalize Lead Resolution", "type": "main", "index": 0}],
                ]
            },
            "Create Lead": {"main": [[{"node": "Finalize Lead Resolution", "type": "main", "index": 0}]]},
            "Finalize Lead Resolution": {"main": [[{"node": "Lead Resolved?", "type": "main", "index": 0}]]},
            "Lead Resolved?": {
                "main": [
                    [{"node": "Patch Lead Appointment", "type": "main", "index": 0}],
                    [{"node": "Reject Unresolved", "type": "main", "index": 0}],
                ]
            },
            "Patch Lead Appointment": {"main": [[{"node": "Insert Appointment Event", "type": "main", "index": 0}]]},
            "Insert Appointment Event": {"main": [[{"node": "Insert Reminder Events", "type": "main", "index": 0}]]},
            "Insert Reminder Events": {"main": [[{"node": "Acknowledge", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _workflow_b2c_demo_call() -> Dict[str, Any]:
    normalize = (
        "const req = items[0]?.json || {};\n"
        "const a = (req.body && typeof req.body === 'object') ? req.body : req;\n"
        "const digits = String(a.phone || '').replace(/\\D/g, '');\n"
        "let phone = null;\n"
        "if (digits.length === 10) phone = '+1' + digits;\n"
        "if (digits.length === 11 && digits[0] === '1') phone = '+' + digits;\n"
        "if (!phone) return [{json:{guardrail_ok:false,reason_code:'invalid_phone',reason_detail:'valid US phone required'}}];\n"
        "return [{json:{guardrail_ok:true,phone,patient_name:a.patient_name || 'Guest',scenario:a.scenario || 'general_inquiry'}}];"
    )
    reject = (
        "return [{json:{status:'rejected',ok:false,reason_code:$json.reason_code || 'invalid_payload',reason_detail:$json.reason_detail || 'guardrail_reject'}}];"
    )
    build_payload = (
        "return [{json:{payload:{"
        "from_number:$node['Config'].json.RETELL_FROM_NUMBER,"
        "to_number:$node['Normalize Demo Request'].json.phone,"
        "override_agent_id:$node['Config'].json.RETELL_AGENT_B2C_ID,"
        "retell_llm_dynamic_variables:{"
        "mode:'patient_demo',"
        "patient_name:$node['Normalize Demo Request'].json.patient_name,"
        "scenario:$node['Normalize Demo Request'].json.scenario"
        "}"
        "}}}];"
    )
    ack = (
        "const data = $json || {};\n"
        "const callId = data.call_id || data.id || null;\n"
        "if (!callId) {\n"
        "  return [{json:{status:'rejected',ok:false,reason_code:'demo_call_failed',reason_detail:data.message || data.error || 'unable to start demo call'}}];\n"
        "}\n"
        "return [{json:{status:'demo_started',ok:true,call_id:callId,call_status:data.call_status || null}}];"
    )
    return {
        "name": "openclaw_retell_fn_b2c_demo_call",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-retell-fn-b2c-demo-call", [20, 20]),
            _cfg_node("2", [220, 20], include_supabase=False, include_retell=True),
            _function_node("3", "Normalize Demo Request", normalize, [440, 20]),
            _if_bool_node("4", "Guardrail OK?", "={{$json.guardrail_ok}}", [660, 20]),
            _function_node("5", "Reject Invalid", reject, [880, -80]),
            _function_node("6", "Build Demo Payload", build_payload, [880, 20]),
            _http_node(
                "7",
                "Retell Demo Call",
                "https://api.retellai.com/v2/create-phone-call",
                "POST",
                [1100, 20],
                json_body_expr="={{JSON.stringify($node[\"Build Demo Payload\"].json.payload)}}",
                headers_expr=_retell_headers_expr(),
                send_body=True,
                continue_on_fail=True,
            ),
            _function_node("8", "Acknowledge", ack, [1320, 20]),
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Config", "type": "main", "index": 0}]]},
            "Config": {"main": [[{"node": "Normalize Demo Request", "type": "main", "index": 0}]]},
            "Normalize Demo Request": {"main": [[{"node": "Guardrail OK?", "type": "main", "index": 0}]]},
            "Guardrail OK?": {
                "main": [
                    [{"node": "Build Demo Payload", "type": "main", "index": 0}],
                    [{"node": "Reject Invalid", "type": "main", "index": 0}],
                ]
            },
            "Build Demo Payload": {"main": [[{"node": "Retell Demo Call", "type": "main", "index": 0}]]},
            "Retell Demo Call": {"main": [[{"node": "Acknowledge", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _workflow_b2c_web_demo() -> Dict[str, Any]:
    prep = (
        "const req = items[0]?.json || {};\n"
        "const a = (req.body && typeof req.body === 'object') ? req.body : req;\n"
        "const firstName = String(a.patient_name || 'Guest').slice(0,80);\n"
        "const scenario = String(a.scenario || 'general_inquiry').slice(0,120);\n"
        "return [{json:{patient_name:firstName,scenario}}];"
    )
    format_out = (
        "const data = $json || {};\n"
        "return [{json:{status:'demo_session_created',ok:true,call_id:data.call_id || null,access_token:data.access_token || null,instructions:'Launch with Retell Web SDK using access_token. Token is intended for immediate test use.'}}];"
    )
    build_payload = (
        "return [{json:{payload:{"
        "agent_id:$node['Config'].json.RETELL_AGENT_B2C_ID,"
        "retell_llm_dynamic_variables:{"
        "mode:'patient_demo_web',"
        "patient_name:$node['Prepare Web Demo'].json.patient_name,"
        "scenario:$node['Prepare Web Demo'].json.scenario"
        "}"
        "}}}];"
    )
    return {
        "name": "openclaw_retell_fn_b2c_web_demo",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-retell-fn-b2c-web-demo", [20, 20]),
            _cfg_node("2", [220, 20], include_supabase=False, include_retell=True),
            _function_node("3", "Prepare Web Demo", prep, [440, 20]),
            _function_node("4", "Build Web Demo Payload", build_payload, [640, 20]),
            _http_node(
                "5",
                "Retell Create Web Call",
                "https://api.retellai.com/v2/create-web-call",
                "POST",
                [860, 20],
                json_body_expr="={{JSON.stringify($node[\"Build Web Demo Payload\"].json.payload)}}",
                headers_expr=_retell_headers_expr(),
                send_body=True,
            ),
            _function_node("6", "Format Response", format_out, [1080, 20]),
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Config", "type": "main", "index": 0}]]},
            "Config": {"main": [[{"node": "Prepare Web Demo", "type": "main", "index": 0}]]},
            "Prepare Web Demo": {"main": [[{"node": "Build Web Demo Payload", "type": "main", "index": 0}]]},
            "Build Web Demo Payload": {"main": [[{"node": "Retell Create Web Call", "type": "main", "index": 0}]]},
            "Retell Create Web Call": {"main": [[{"node": "Format Response", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _workflow_b2c_showrate_nudge() -> Dict[str, Any]:
    build = (
        "const rows = Array.isArray(items[0]?.json) ? items[0].json : [];\n"
        "const now = Date.now();\n"
        "const out = [];\n"
        "for (const lead of rows) {\n"
        "  if (!lead || !lead.id || !lead.phone || !lead.next_touch_at) continue;\n"
        "  const appt = new Date(lead.next_touch_at).getTime();\n"
        "  if (!Number.isFinite(appt) || appt <= now) continue;\n"
        "  const hours = (appt - now) / 3600000;\n"
        "  let window = null;\n"
        "  if (hours >= 22 && hours <= 26) window = 'H24';\n"
        "  else if (hours >= 1 && hours <= 3) window = 'H2';\n"
        "  if (!window) continue;\n"
        "  const dateKey = new Date(appt).toISOString().slice(0,10);\n"
        "  const idem = `${lead.id}-showrate-${window}-${dateKey}`;\n"
        "  out.push({json:{lead,window,appointment_at_iso:new Date(appt).toISOString(),idempotency_key:idem}});\n"
        "}\n"
        "return out;"
    )
    return {
        "name": "openclaw_b2c_showrate_nudge",
        "nodes": [
            _webhook_node("1", "Webhook Trigger", "openclaw-b2c-showrate-nudge", [20, 20]),
            _cfg_node("2", [220, 20], include_supabase=True, include_retell=True),
            _http_node(
                "3",
                "Fetch Qualified Leads",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/leads?select=id,business_name,phone,email,next_touch_at,status&status=eq.QUALIFIED&phone=not.is.null&next_touch_at=not.is.null&limit=500",
                "GET",
                [440, 20],
                headers_expr=_supabase_headers_expr(),
                send_body=False,
            ),
            _function_node("4", "Build Reminder Candidates", build, [660, 20]),
            _split_node("5", "Split Candidates", [880, 20]),
            _http_node(
                "6",
                "Insert Reminder Event",
                "={{$node[\"Config\"].json.SUPABASE_URL}}/rest/v1/lead_events?on_conflict=idempotency_key",
                "POST",
                [1100, 20],
                json_body_expr="={{JSON.stringify({lead_id:$json.lead.id,place_id:null,event_type:'b2c_showrate_reminder_sent',idempotency_key:$json.idempotency_key,payload_json:{window:$json.window,appointment_at_iso:$json.appointment_at_iso,channel_order:['email','voice']}})}}",
                headers_expr=_supabase_headers_expr("resolution=ignore-duplicates,return=representation"),
                send_body=True,
            ),
            _if_number_node("7", "Is New Event?", "={{$json.length || 0}}", "larger", 0, [1320, 20]),
            _http_node(
                "8",
                "Retell Reminder Call",
                "https://api.retellai.com/v2/create-phone-call",
                "POST",
                [1540, 20],
                json_body_expr="={{JSON.stringify({\"from_number\":$node[\"Config\"].json.RETELL_FROM_NUMBER,\"to_number\":$node[\"Build Reminder Candidates\"].json.lead.phone,\"override_agent_id\":$node[\"Config\"].json.RETELL_AGENT_B2C_ID,\"retell_llm_dynamic_variables\":{\"mode\":\"appointment_reminder\",\"window\":$node[\"Build Reminder Candidates\"].json.window,\"appointment_at_iso\":$node[\"Build Reminder Candidates\"].json.appointment_at_iso,\"business_name\":$node[\"Build Reminder Candidates\"].json.lead.business_name || \"\"}})}}",
                headers_expr=_retell_headers_expr(),
                send_body=True,
                continue_on_fail=True,
            ),
            _function_node("9", "Done", "return [{json:{status:'ok'}}];", [1760, 20]),
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Config", "type": "main", "index": 0}]]},
            "Config": {"main": [[{"node": "Fetch Qualified Leads", "type": "main", "index": 0}]]},
            "Fetch Qualified Leads": {"main": [[{"node": "Build Reminder Candidates", "type": "main", "index": 0}]]},
            "Build Reminder Candidates": {"main": [[{"node": "Split Candidates", "type": "main", "index": 0}]]},
            "Split Candidates": {"main": [[{"node": "Insert Reminder Event", "type": "main", "index": 0}]]},
            "Insert Reminder Event": {"main": [[{"node": "Is New Event?", "type": "main", "index": 0}]]},
            "Is New Event?": {
                "main": [
                    [{"node": "Retell Reminder Call", "type": "main", "index": 0}],
                    [{"node": "Done", "type": "main", "index": 0}],
                ]
            },
            "Retell Reminder Call": {"main": [[{"node": "Done", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _workflows() -> List[Tuple[str, Dict[str, Any], bool]]:
    return [
        ("openclaw_retell_fn_b2c_context.json", _workflow_b2c_context(), True),
        ("openclaw_retell_fn_b2c_availability.json", _workflow_b2c_availability(), True),
        ("openclaw_retell_fn_b2c_quote.json", _workflow_b2c_quote(), True),
        ("openclaw_retell_fn_b2c_book_appointment.json", _workflow_b2c_book_appointment(), True),
        ("openclaw_retell_fn_b2c_demo_call.json", _workflow_b2c_demo_call(), True),
        ("openclaw_retell_fn_b2c_web_demo.json", _workflow_b2c_web_demo(), True),
        ("openclaw_b2c_showrate_nudge.json", _workflow_b2c_showrate_nudge(), False),
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
    rows = _list_remote_workflows()
    existing = next((r for r in rows if r.get("name") == name), None)
    if not existing:
        return "not_found"
    wid = existing["id"]
    detail = requests.get(f"{_n8n_base()}/workflows/{wid}", headers=_n8n_headers(), timeout=30).json()
    data = detail.get("data", detail)
    if bool(data.get("active")):
        return "already_active"
    resp = requests.post(f"{_n8n_base()}/workflows/{wid}/activate", headers=_n8n_headers(), timeout=30)
    if resp.status_code >= 400:
        return f"failed:{resp.status_code}"
    return "ok"


def _upsert_showrate_cron_job() -> str:
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
        "name": "cron:openclaw-b2c-showrate-nudge",
        "cron": "5 * * * *",
        "task_type": "n8n.trigger",
        "payload_json": {"workflow": "openclaw-b2c-showrate-nudge", "data": {}},
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
    for filename, wf, mcp_enable in _workflows():
        out = WORKFLOWS_DIR / filename
        out.write_text(json.dumps(wf, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        report["local_files"].append(str(out))
        status = _upsert_remote(wf)
        report["remote"][wf["name"]] = status
        report["remote"][f"{wf['name']}:active"] = _activate_workflow(wf["name"])
        if mcp_enable:
            report["remote"][f"{wf['name']}:mcp"] = _enable_mcp(wf["name"])
    report["showrate_cron"] = _upsert_showrate_cron_job()
    print(json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
