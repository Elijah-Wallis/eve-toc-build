#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import requests


TARGET_NAMES = [
    "openclaw_retell_call_dispatch",
    "openclaw_nurture_engine",
    "openclaw_retell_postcall_ingest",
    "openclaw_apify_scrape_ingest",
]


def _mcp_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }


def _extract_sse_json(text: str) -> Dict[str, Any]:
    for line in text.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: ") :])
    raise RuntimeError("No SSE data line found in response")


def _mcp_call(url: str, token: str, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = requests.post(url, headers=_mcp_headers(token), json=payload, timeout=30)
    resp.raise_for_status()
    return _extract_sse_json(resp.text)


def main() -> int:
    mcp_url = os.environ.get("N8N_MCP_URL", "").strip()
    token = (os.environ.get("N8N_MCP_TOKEN") or os.environ.get("N8N_MCP_ACCESS_TOKEN") or "").strip()
    if not mcp_url or not token:
        raise RuntimeError("N8N_MCP_URL and N8N_MCP_TOKEN/N8N_MCP_ACCESS_TOKEN are required")

    tools_obj = _mcp_call(mcp_url, token, "tools/list", {})
    tools = tools_obj.get("result", {}).get("tools", [])
    tool_names = [tool.get("name") for tool in tools if tool.get("name")]
    required_tools = {"search_workflows", "execute_workflow", "get_workflow_details"}
    missing_tools = sorted(required_tools - set(tool_names))

    workflow_visibility: List[Dict[str, Any]] = []
    for name in TARGET_NAMES:
        search = _mcp_call(mcp_url, token, "tools/call", {"name": "search_workflows", "arguments": {"query": name, "limit": 10}})
        structured = search.get("result", {}).get("structuredContent", {})
        data = structured.get("data", []) if isinstance(structured, dict) else []
        matched = [row for row in data if row.get("name") == name]
        workflow_visibility.append({"name": name, "visible": bool(matched), "count": len(matched)})

    result = {
        "mcp_url": mcp_url,
        "tools_present": sorted(tool_names),
        "missing_tools": missing_tools,
        "workflow_visibility": workflow_visibility,
        "ok": not missing_tools and all(row["visible"] for row in workflow_visibility),
    }
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
