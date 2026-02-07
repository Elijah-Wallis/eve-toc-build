#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import requests


TOOL_BLOCK_MARKER = "## TOOL ORCHESTRATION (B2C AUTOMATION-FIRST)"
DEFAULT_PROMPT_FILE = "Business_Code/retell_system_prompt_medspa_b2c_v1.md"
DEFAULT_KB_FILE = "Business_Code/retell_kb_medspa_b2c.md"

TOOL_BLOCK_TEXT = (
    "## TOOL ORCHESTRATION (B2C AUTOMATION-FIRST)\n"
    "1. Start with `b2c_context_brief` for personalized trust framing.\n"
    "2. Use `b2c_quote_estimate` only for bounded estimates (never exact final price).\n"
    "3. Use `b2c_check_availability` before offering times.\n"
    "4. On acceptance, use `b2c_book_appointment` with timezone + appointment_at_iso.\n"
    "5. If prospect asks to test, use `b2c_start_free_demo_call` or `b2c_create_web_demo_session`.\n"
    "6. Before call end, log via `log_call_insight` and set next action via `set_follow_up_plan`.\n"
    "7. If user requests no contact, call `mark_do_not_call` immediately.\n"
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
            "name": "b2c_context_brief",
            "description": "Personalized trust opener and next-step framing for patient inquiries.",
            "url": "https://elijah-wallis.app.n8n.cloud/webhook/openclaw-retell-fn-b2c-context",
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
            "url": "https://elijah-wallis.app.n8n.cloud/webhook/openclaw-retell-fn-b2c-quote",
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
            "url": "https://elijah-wallis.app.n8n.cloud/webhook/openclaw-retell-fn-b2c-availability",
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
            "url": "https://elijah-wallis.app.n8n.cloud/webhook/openclaw-retell-fn-b2c-book-appointment",
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
            "url": "https://elijah-wallis.app.n8n.cloud/webhook/openclaw-retell-fn-b2c-demo-call",
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
            "url": "https://elijah-wallis.app.n8n.cloud/webhook/openclaw-retell-fn-b2c-web-demo",
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
            "description": "Set/adjust next touch timing and qualification state.",
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
            "description": "Immediately suppress future outreach when patient opts out.",
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
    parser = argparse.ArgumentParser(description="Configure Retell B2C agent with KB + booking/demo tools.")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--kb-file", default=DEFAULT_KB_FILE)
    parser.add_argument("--kb-name", default="MedSpa B2C Patient Conversion KB")
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

    # Retell B2C LLM updates reject MCP creation in this endpoint unless MCP ids already exist.
    # Keep existing MCP objects only, and normalize N8N MCP fields when present.
    mcps = llm.get("mcps", []) or []
    mcp_token = os.environ.get("N8N_MCP_TOKEN", "").strip()
    for mcp in mcps:
        if mcp.get("name") == "N8N MCP" or mcp.get("url") == "https://elijah-wallis.app.n8n.cloud/mcp-server/http":
            mcp["name"] = "N8N MCP"
            mcp["url"] = "https://elijah-wallis.app.n8n.cloud/mcp-server/http"
            mcp["timeout_ms"] = 10000
            if mcp_token:
                mcp["headers"] = {"Authorization": f"Bearer {mcp_token}"}
            mcp["query_params"] = mcp.get("query_params", {})

    patch_payload: Dict[str, Any] = {
        "general_tools": merged_tools,
        "general_prompt": _resolve_general_prompt(llm.get("general_prompt", ""), Path(args.prompt_file).resolve()),
        "knowledge_base_ids": knowledge_base_ids,
        "kb_config": {"top_k": 5, "filter_score": 0.45},
    }
    if mcps:
        patch_payload["mcps"] = mcps
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
