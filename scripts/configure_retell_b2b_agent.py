#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import requests


TOOL_BLOCK_MARKER = "## TOOL ORCHESTRATION (AUTOMATION-FIRST)"
DEFAULT_PROMPT_FILE = "Business_Code/retell_system_prompt_medspa_b2b_v21.md"

TOOL_BLOCK_TEXT = (
    "## TOOL ORCHESTRATION (AUTOMATION-FIRST)\n"
    "1. Before positioning the offer, call `enrich_lead_intel` with lead_id plus business_name/city/state/website/email to refresh intel.\n"
    "2. Early in call (after intro), call `get_lead_context` with business_name, city, state, rating, reviews_count, touch_count, and known website/category.\n"
    "3. Before first concrete offer/CTA, call `recommend_offer_angle` with touch_count, positive_signal, rating, reviews_count.\n"
    "4. If user asks to stop contact, call `mark_do_not_call` immediately with phone and reason.\n"
    "5. Before ending any meaningful call, call `log_call_insight` with outcome, objection, notes, next_step, and lead_id/phone/business_name.\n"
    "6. When follow-up is agreed, call `set_follow_up_plan` with lead_id or phone plus next_touch_at and status.\n"
    "7. Keep tool payloads factual; do not hallucinate unknown fields.\n"
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


def _build_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "custom",
            "name": "enrich_lead_intel",
            "description": "Pull fresh business intelligence on-demand (Apify + Supabase context) before pitching.",
            "url": "https://elijah-wallis.app.n8n.cloud/webhook/openclaw-retell-fn-enrich-intel",
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
            "url": "https://elijah-wallis.app.n8n.cloud/webhook/openclaw-retell-fn-context-brief",
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
            "url": "https://elijah-wallis.app.n8n.cloud/webhook/openclaw-retell-fn-offer-angle",
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
            "description": "Persist objection, outcome, decision-maker clues, and notes for continuous learning.",
            "url": "https://elijah-wallis.app.n8n.cloud/webhook/openclaw-retell-fn-log-insight",
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
            "url": "https://elijah-wallis.app.n8n.cloud/webhook/openclaw-retell-fn-set-followup",
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
            "description": "Immediately block future outreach for a phone number when user requests no further contact.",
            "url": "https://elijah-wallis.app.n8n.cloud/webhook/openclaw-retell-fn-mark-dnc",
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
    parser = argparse.ArgumentParser(description="Configure Retell B2B agent with KB + personalization tools.")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--kb-file", default="Business_Code/retell_kb_medspa_b2b.md")
    parser.add_argument("--kb-name", default="MedSpa B2B TX Knowledge Base")
    parser.add_argument("--prompt-file", default=DEFAULT_PROMPT_FILE)
    parser.add_argument("--skip-kb-upload", action="store_true")
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
    new_tools = _build_tools()
    new_names = {t["name"] for t in new_tools}
    existing_tools = [t for t in existing_tools if t.get("name") not in new_names]
    merged_tools = existing_tools + new_tools

    mcps = llm.get("mcps", []) or []
    mcp_token = os.environ.get("N8N_MCP_TOKEN", "").strip()
    found = False
    for mcp in mcps:
        if mcp.get("name") == "N8N MCP" or mcp.get("url") == "https://elijah-wallis.app.n8n.cloud/mcp-server/http":
            mcp["name"] = "N8N MCP"
            mcp["url"] = "https://elijah-wallis.app.n8n.cloud/mcp-server/http"
            mcp["timeout_ms"] = 10000
            if mcp_token:
                mcp["headers"] = {"Authorization": f"Bearer {mcp_token}"}
            mcp["query_params"] = mcp.get("query_params", {})
            found = True
    if not found:
        mcps.append(
            {
                "name": "N8N MCP",
                "url": "https://elijah-wallis.app.n8n.cloud/mcp-server/http",
                "headers": {"Authorization": f"Bearer {mcp_token}"} if mcp_token else {},
                "query_params": {},
                "timeout_ms": 10000,
            }
        )

    patch_payload = {
        "general_tools": merged_tools,
        "general_prompt": _resolve_general_prompt(llm.get("general_prompt", ""), Path(args.prompt_file).resolve()),
        "mcps": mcps,
        "knowledge_base_ids": knowledge_base_ids,
        "kb_config": {"top_k": 5, "filter_score": 0.45},
    }
    resp = requests.patch(
        f"https://api.retellai.com/update-retell-llm/{llm_id}",
        headers=_retell_headers(api_key, json_body=True),
        json=patch_payload,
        timeout=90,
    )
    resp.raise_for_status()
    updated = resp.json()
    print(
        json.dumps(
            {
                "agent_id": args.agent_id,
                "llm_id": llm_id,
                "created_kb_id": created_kb_id,
                "knowledge_base_ids": updated.get("knowledge_base_ids"),
                "tool_count": len(updated.get("general_tools", [])),
                "mcp_count": len(updated.get("mcps", [])),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
