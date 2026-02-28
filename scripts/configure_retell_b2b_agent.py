#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


V5_PROMPT_FILE = "Business_Code/retell_system_prompt_medspa_b2b_v50_golden_master.md"
V6_PROMPT_FILE = "Business_Code/retell_system_prompt_medspa_b2b_v60_diamond.md"
V133_PROMPT_FILE = "mcp_servers/b2b_workflow.yaml"
DEFAULT_PROMPT_VERSION = "v13.3"
DEFAULT_N8N_WEBHOOK_BASE = "https://elijah-wallis.app.n8n.cloud"
DEFAULT_N8N_MCP_URL = "https://elijah-wallis.app.n8n.cloud/mcp-server/http"
DEFAULT_RETELL_AGENT_UPDATE_BASE = "https://api.retellai.com"


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


def _resolve_prompt_file(prompt_version: str) -> str:
    version = (prompt_version or DEFAULT_PROMPT_VERSION).strip().lower()
    if version == "v5":
        return V5_PROMPT_FILE
    if version in {"v13", "v13.3", "v133"}:
        return V133_PROMPT_FILE
    return V6_PROMPT_FILE


def _build_tools(webhook_base: str) -> List[Dict[str, Any]]:
    base = webhook_base.rstrip("/")
    return [
        {
            "type": "custom",
            "name": "send_evidence_package",
            "description": "Send evidence package via email and optional SMS summary with strict delivery guardrails.",
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
            "name": "mark_dnc_compliant",
            "description": "Immediately mark a number as do-not-call compliant.",
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
            "description": "Persist call outcome and concise analytics context for Revenue Ops.",
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
            "description": "Pull fresh business intelligence on-demand (Apify + Supabase context) before pitching.",
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
            "name": "get_lead_context",
            "description": "Return personalized opener, value framing, and discovery questions using known lead attributes.",
            "url": f"{base}/webhook/openclaw-retell-fn-context-brief",
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
            "name": "context_brief",
            "description": "Compatibility alias for get_lead_context.",
            "url": f"{base}/webhook/openclaw-retell-fn-context-brief",
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
            "name": "recommend_offer_angle",
            "description": "Return next-best offer angle and short script based on signal quality and touch history.",
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
            "name": "get_offer_recommendation",
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
            "name": "log_call_insight",
            "description": "Compatibility alias for legacy scripts that still call log_call_insight.",
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
            "description": "Set next-touch timing and qualification flags on a lead record.",
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
            "name": "mark_do_not_call",
            "description": "Compatibility alias for mark_dnc_compliant.",
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


def _resolve_general_prompt(current_prompt: str, prompt_file: Path) -> str:
    if prompt_file.exists():
        loaded = prompt_file.read_text(encoding="utf-8").strip()
        if loaded:
            return loaded
    return current_prompt


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure Retell B2B agent with KB + personalization tools.")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--kb-file", default="Business_Code/retell_kb_medspa_b2b.md")
    parser.add_argument("--kb-name", default="MedSpa B2B TX Knowledge Base")
    parser.add_argument("--prompt-version", choices=["v5", "v6", "v13.3"], default=DEFAULT_PROMPT_VERSION)
    parser.add_argument("--prompt-file", default="", help="Optional explicit prompt file override.")
    parser.add_argument("--skip-kb-upload", action="store_true")
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

    project_root = Path(__file__).resolve().parents[1]
    kb_file = Path(args.kb_file).resolve()
    if not kb_file.exists() and not args.skip_kb_upload:
        raise FileNotFoundError(f"Knowledge base file not found: {kb_file}")
    prompt_rel = args.prompt_file.strip() or _resolve_prompt_file(args.prompt_version)
    prompt_file = (project_root / prompt_rel).resolve()
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

    webhook_base = os.environ.get("N8N_PUBLIC_WEBHOOK_BASE", DEFAULT_N8N_WEBHOOK_BASE).strip().rstrip("/")
    if not webhook_base:
        webhook_base = DEFAULT_N8N_WEBHOOK_BASE

    agent = _get_agent(api_key, args.agent_id)
    llm_id = agent["response_engine"]["llm_id"]
    llm = _get_llm(api_key, llm_id)

    knowledge_base_ids = llm.get("knowledge_base_ids", [])
    created_kb_id = None
    if not args.skip_kb_upload:
        created_kb_id = _create_knowledge_base(api_key, args.kb_name, kb_file)
        knowledge_base_ids = [created_kb_id]

    existing_tools = llm.get("general_tools", []) or []
    new_tools = _build_tools(webhook_base)
    new_names = {t["name"] for t in new_tools}
    existing_tools = [t for t in existing_tools if t.get("name") not in new_names]
    merged_tools = existing_tools + new_tools

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
                "name": "N8N MCP",
                "url": mcp_url,
                "headers": {"Authorization": f"Bearer {mcp_token}"} if mcp_token else {},
                "query_params": {},
                "timeout_ms": 10000,
            }
        )

    patch_payload = {
        "general_tools": merged_tools,
        "general_prompt": _resolve_general_prompt(llm.get("general_prompt", ""), prompt_file),
        "mcps": mcps,
        "knowledge_base_ids": knowledge_base_ids,
        "kb_config": {"top_k": 8, "filter_score": 0.35},
    }
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
                "prompt_version": args.prompt_version,
                "prompt_file": str(prompt_file),
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
