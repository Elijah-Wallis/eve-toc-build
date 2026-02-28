#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


TOOL_BLOCK_MARKER = "## TOOL ORCHESTRATION (B2C AUTOMATION-FIRST)"
DEFAULT_PROMPT_FILE = "Business_Code/retell_system_prompt_medspa_b2c_v1.md"
DEFAULT_KB_FILE = "Business_Code/retell_kb_medspa_b2c.md"
DEFAULT_N8N_WEBHOOK_BASE = "https://elijah-wallis.app.n8n.cloud"
DEFAULT_N8N_MCP_URL = "https://elijah-wallis.app.n8n.cloud/mcp-server/http"
DEFAULT_RETELL_AGENT_UPDATE_BASE = "https://api.retellai.com"

TOOL_BLOCK_TEXT = (
    "## TOOL ORCHESTRATION (B2C AUTOMATION-FIRST)\n"
    "1. Start with `b2c_context_brief` for personalized trust framing.\n"
    "2. Use `b2c_quote_estimate` only for bounded estimates (never exact final price).\n"
    "3. Use `b2c_check_availability` before offering times.\n"
    "4. On acceptance, use `b2c_book_appointment` with timezone + appointment_at_iso.\n"
    "5. If prospect asks to test, use `b2c_start_free_demo_call` or `b2c_create_web_demo_session`.\n"
    "6. For hard objections, use `enrich_lead_intel` and `recommend_offer_angle`.\n"
    "7. Before call end, log via `log_call_outcome` (or `log_call_insight`) and set next action via `set_follow_up_plan`.\n"
    "8. If recap artifact is promised, use `send_evidence_package`.\n"
    "9. If user requests no contact, call `mark_dnc_compliant` (or `mark_do_not_call`) immediately.\n"
)


def _retell_headers(api_key: str, json_body: bool = False) -> Dict[str, str]:
    headers = {"Authorization": f"Bearer {api_key}"}
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _get_agent(api_key: str, agent_id: str) -> Dict[str, Any]:
    resp = requests.get(
        f"https://api.retellai.com/get-agent/{agent_id}",
        headers=_retell_headers(api_key),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _get_llm(api_key: str, llm_id: str) -> Dict[str, Any]:
    resp = requests.get(
        f"https://api.retellai.com/get-retell-llm/{llm_id}",
        headers=_retell_headers(api_key),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _create_knowledge_base(api_key: str, kb_name: str, kb_file: Path) -> str:
    with kb_file.open("rb") as fh:
        files = {"knowledge_base_files": (kb_file.name, fh, "text/markdown")}
        data = {"knowledge_base_name": kb_name}
        resp = requests.post(
            "https://api.retellai.com/create-knowledge-base",
            headers=_retell_headers(api_key),
            data=data,
            files=files,
            timeout=120,
        )
    resp.raise_for_status()
    body = resp.json()
    return body["knowledge_base_id"]


def _short_error(text: str, limit: int = 220) -> str:
    clean = " ".join((text or "").strip().split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."


def _update_agent_bidirectional(
    api_key: str,
    agent_id: str,
    agent: Dict[str, Any],
    websocket_url: str,
    bidirectional_enabled: bool,
) -> Dict[str, Any]:
    if not websocket_url:
        return {"status": "skipped", "reason": "no_websocket_url"}

    base_url = os.environ.get("RETELL_API_BASE", DEFAULT_RETELL_AGENT_UPDATE_BASE).rstrip("/")
    response_engine = dict(agent.get("response_engine") or {})
    response_engine["llm_websocket_url"] = websocket_url
    response_engine["auto_reconnect"] = True
    response_engine["type"] = response_engine.get("type") or "custom-llm-websocket"
    response_engine["streaming_mode"] = "bidirectional" if bidirectional_enabled else "unidirectional"
    response_engine["ping_pong_interval_ms"] = 2000
    response_engine["ping_timeout_ms"] = 5000

    payload = {"response_engine": response_engine}
    if bidirectional_enabled:
        payload["enable_bidirectional_audio"] = True
        payload["interrupt_on_user_speech"] = True
        payload["allow_barge_in"] = True

    attempts: List[Dict[str, Any]] = []
    candidates = [
        ("patch", f"{base_url}/update-agent/{agent_id}", payload),
        ("patch", f"{base_url}/update-agent", dict(payload, agent_id=agent_id)),
        ("post", f"{base_url}/update-agent", dict(payload, agent_id=agent_id)),
    ]

    for method, url, body in candidates:
        try:
            if method == "patch":
                resp = requests.patch(url, headers=_retell_headers(api_key, json_body=True), json=body, timeout=45)
            else:
                resp = requests.post(url, headers=_retell_headers(api_key, json_body=True), json=body, timeout=45)
            attempts.append({"method": method, "url": url, "status_code": resp.status_code})
            if resp.status_code < 400:
                return {"status": "updated", "endpoint": url, "status_code": resp.status_code, "attempts": attempts}
            attempts[-1]["error"] = _short_error(resp.text)
        except requests.RequestException as exc:
            attempts.append({"method": method, "url": url, "error": _short_error(str(exc))})
    return {"status": "failed", "attempts": attempts}


def _build_tools(webhook_base: str) -> List[Dict[str, Any]]:
    base = webhook_base.rstrip("/")
    return [
        {
            "type": "custom",
            "name": "b2c_context_brief",
            "description": "Personalized trust opener and next-step framing for patient inquiries.",
            "url": f"{base}/webhook/openclaw-retell-fn-b2c-context",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 20000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "get_lead_context",
            "description": "Compatibility alias for b2c_context_brief.",
            "url": f"{base}/webhook/openclaw-retell-fn-b2c-context",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 20000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "b2c_quote_estimate",
            "description": "Return bounded price ranges and compliant pricing disclaimer.",
            "url": f"{base}/webhook/openclaw-retell-fn-b2c-quote",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 20000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "b2c_check_availability",
            "description": "Generate near-term appointment options in the requested timezone.",
            "url": f"{base}/webhook/openclaw-retell-fn-b2c-availability",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 20000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "b2c_book_appointment",
            "description": "Book appointment, update lead status, and pre-schedule show-rate reminders.",
            "url": f"{base}/webhook/openclaw-retell-fn-b2c-book-appointment",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 30000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "b2c_start_free_demo_call",
            "description": "Start immediate no-cost-to-prospect live demo callback using B2C agent.",
            "url": f"{base}/webhook/openclaw-retell-fn-b2c-demo-call",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 30000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "b2c_create_web_demo_session",
            "description": "Create a web demo session token for self-serve stress testing.",
            "url": f"{base}/webhook/openclaw-retell-fn-b2c-web-demo",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 30000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "log_call_insight",
            "description": "Persist outcome, objection, and notes for B2C learning loop.",
            "url": f"{base}/webhook/openclaw-retell-fn-log-insight",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 25000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "set_follow_up_plan",
            "description": "Set/adjust next touch timing and qualification state.",
            "url": f"{base}/webhook/openclaw-retell-fn-set-followup",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 25000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "set_followup",
            "description": "Compatibility alias for set_follow_up_plan.",
            "url": f"{base}/webhook/openclaw-retell-fn-set-followup",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 25000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "mark_dnc_compliant",
            "description": "Immediate do-not-call suppression for compliance.",
            "url": f"{base}/webhook/openclaw-retell-fn-mark-dnc",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 15000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "log_call_outcome",
            "description": "Structured outcome logging alias for analytics and coaching.",
            "url": f"{base}/webhook/openclaw-retell-fn-log-insight",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 25000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "enrich_lead_intel",
            "description": "Fetch latest business/persona context before handling complex objections.",
            "url": f"{base}/webhook/openclaw-retell-fn-enrich-intel",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 120000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "recommend_offer_angle",
            "description": "Return best next offer framing based on patient signals and touch history.",
            "url": f"{base}/webhook/openclaw-retell-fn-offer-angle",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 20000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "offer_angle",
            "description": "Compatibility alias for recommend_offer_angle.",
            "url": f"{base}/webhook/openclaw-retell-fn-offer-angle",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 20000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "send_evidence_package",
            "description": "Deliver recap artifacts by email/SMS after significant booking or escalation events.",
            "url": f"{base}/webhook/openclaw-retell-fn-send-evidence-package",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 25000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
        {
            "type": "custom",
            "name": "mark_do_not_call",
            "description": "Immediately suppress future outreach when patient opts out.",
            "url": f"{base}/webhook/openclaw-retell-fn-mark-dnc",
            "method": "POST",
            "parameter_type": "json",
            "args_at_root": False,
            "headers": {},
            "query_params": {},
            "timeout_ms": 15000,
            "speak_during_execution": False,
            "speak_after_execution": False,
            "response_variables": {},
        },
    ]


def _upsert_tool_block(prompt: str) -> str:
    base = prompt or ""
    if TOOL_BLOCK_MARKER in base:
        base = base[: base.index(TOOL_BLOCK_MARKER)].rstrip()
    return base.rstrip() + "\n\n" + TOOL_BLOCK_TEXT


def _resolve_general_prompt(current_prompt: str, prompt_file: Path) -> str:
    if prompt_file.exists():
        loaded = prompt_file.read_text(encoding="utf-8").strip()
        if loaded:
            return _upsert_tool_block(loaded)
    return _upsert_tool_block(current_prompt)


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure Retell B2C agent with KB + booking/demo tools.")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--kb-file", default=DEFAULT_KB_FILE)
    parser.add_argument("--kb-name", default="MedSpa B2C Patient Conversion KB")
    parser.add_argument("--prompt-file", default=DEFAULT_PROMPT_FILE)
    parser.add_argument("--skip-kb-upload", action="store_true")
    parser.add_argument("--webhook-base", default="", help="Override n8n webhook base URL.")
    parser.add_argument("--websocket-url", default="", help="Custom LLM websocket URL for bidirectional mode.")
    parser.add_argument(
        "--bidirectional-mode",
        choices=["on", "off"],
        default="on",
        help="Apply bidirectional streaming flags when updating agent websocket settings.",
    )
    parser.add_argument(
        "--strict-agent-update",
        action="store_true",
        help="Fail if websocket agent update is requested but cannot be applied.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("RETELL_AI_KEY", "")
    if not api_key:
        raise RuntimeError("RETELL_AI_KEY is required")

    kb_file = Path(args.kb_file).resolve()
    if not kb_file.exists() and not args.skip_kb_upload:
        raise FileNotFoundError(f"Knowledge base file not found: {kb_file}")

    agent = _get_agent(api_key, args.agent_id)
    llm_id = agent["response_engine"]["llm_id"]
    llm = _get_llm(api_key, llm_id)

    knowledge_base_ids = llm.get("knowledge_base_ids", [])
    created_kb_id = None
    if not args.skip_kb_upload:
        created_kb_id = _create_knowledge_base(api_key, args.kb_name, kb_file)
        knowledge_base_ids = [created_kb_id]

    existing_tools = llm.get("general_tools", []) or []
    webhook_base = args.webhook_base.strip() or os.environ.get("N8N_PUBLIC_WEBHOOK_BASE", DEFAULT_N8N_WEBHOOK_BASE).strip().rstrip("/")
    if not webhook_base:
        webhook_base = DEFAULT_N8N_WEBHOOK_BASE
    new_tools = _build_tools(webhook_base)
    new_names = {t["name"] for t in new_tools}
    existing_tools = [t for t in existing_tools if t.get("name") not in new_names]
    merged_tools = existing_tools + new_tools

    # Retell B2C LLM updates reject MCP creation in this endpoint unless MCP ids already exist.
    # Keep existing MCP objects only, and normalize N8N MCP fields when present.
    original_mcps = llm.get("mcps", []) or []
    mcps = list(original_mcps)
    mcp_token = os.environ.get("N8N_MCP_TOKEN", "").strip()
    mcp_url = os.environ.get("N8N_MCP_URL", DEFAULT_N8N_MCP_URL).strip() or DEFAULT_N8N_MCP_URL
    attach_new_mcp = os.environ.get("OPENCLAW_RETELL_ATTACH_N8N_MCP", "0") == "1"
    found = False
    for mcp in mcps:
        if mcp.get("name") == "N8N MCP" or mcp.get("url") in {DEFAULT_N8N_MCP_URL, mcp_url}:
            mcp["name"] = "N8N MCP"
            mcp["url"] = mcp_url
            mcp["timeout_ms"] = 10000
            if mcp_token:
                mcp["headers"] = {"Authorization": f"Bearer {mcp_token}"}
            mcp["query_params"] = mcp.get("query_params", {})
            found = True
    if not found and attach_new_mcp:
        mcps.append(
            {
                "id": f"mcp-{int(time.time() * 1000)}",
                "name": "N8N MCP",
                "url": mcp_url,
                "headers": {"Authorization": f"Bearer {mcp_token}"} if mcp_token else {},
                "query_params": {},
                "timeout_ms": 10000,
            }
        )

    patch_payload: Dict[str, Any] = {
        "general_tools": merged_tools,
        "general_prompt": _resolve_general_prompt(llm.get("general_prompt", ""), Path(args.prompt_file).resolve()),
        "knowledge_base_ids": knowledge_base_ids,
        "kb_config": {"top_k": 8, "filter_score": 0.35},
    }
    if mcps:
        patch_payload["mcps"] = mcps
    resp = requests.patch(
        f"https://api.retellai.com/update-retell-llm/{llm_id}",
        headers=_retell_headers(api_key, json_body=True),
        json=patch_payload,
        timeout=90,
    )
    if resp.status_code >= 400 and patch_payload.get("mcps") != original_mcps:
        fallback_payload = dict(patch_payload)
        fallback_payload["mcps"] = original_mcps
        resp = requests.patch(
            f"https://api.retellai.com/update-retell-llm/{llm_id}",
            headers=_retell_headers(api_key, json_body=True),
            json=fallback_payload,
            timeout=90,
        )
    resp.raise_for_status()
    updated = resp.json()

    websocket_url = args.websocket_url.strip() or os.environ.get("RETELL_LLM_WEBSOCKET_URL", "").strip()
    bidirectional_enabled = args.bidirectional_mode == "on"
    agent_update_result: Optional[Dict[str, Any]] = None
    if websocket_url:
        agent_update_result = _update_agent_bidirectional(
            api_key=api_key,
            agent_id=args.agent_id,
            agent=agent,
            websocket_url=websocket_url,
            bidirectional_enabled=bidirectional_enabled,
        )
        if args.strict_agent_update and agent_update_result.get("status") != "updated":
            raise RuntimeError(f"Retell agent websocket update failed: {agent_update_result}")

    print(
        json.dumps(
            {
                "agent_id": args.agent_id,
                "llm_id": llm_id,
                "created_kb_id": created_kb_id,
                "knowledge_base_ids": updated.get("knowledge_base_ids"),
                "tool_count": len(updated.get("general_tools", [])),
                "mcp_count": len(updated.get("mcps", [])),
                "webhook_base": webhook_base,
                "websocket_url": websocket_url or None,
                "bidirectional_mode": "on" if bidirectional_enabled else "off",
                "agent_update": agent_update_result or {"status": "skipped", "reason": "no_websocket_url"},
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
