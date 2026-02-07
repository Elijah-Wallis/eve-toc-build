from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict

import requests


def _json_response(handler: BaseHTTPRequestHandler, payload: Dict[str, Any], status: int = 200) -> None:
    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _retell_headers() -> Dict[str, str]:
    token = os.environ.get("RETELL_AI_KEY")
    if not token:
        raise RuntimeError("RETELL_AI_KEY is not set")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _retell_base() -> str:
    return os.environ.get("RETELL_BASE_URL", "https://api.retellai.com").rstrip("/")


def _mcp_tools_list() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "retell.create_phone_call",
                "description": "Create outbound Retell phone call",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "from_number": {"type": "string"},
                        "to_number": {"type": "string"},
                        "override_agent_id": {"type": "string"},
                        "retell_llm_dynamic_variables": {"type": "object"},
                    },
                    "required": ["from_number", "to_number", "override_agent_id"],
                },
            },
            {
                "name": "retell.create_web_call",
                "description": "Create web demo call session via Retell and return access_token",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string"},
                        "retell_llm_dynamic_variables": {"type": "object"},
                    },
                    "required": ["agent_id"],
                },
            },
            {
                "name": "retell.get_call",
                "description": "Fetch Retell call by call_id",
                "inputSchema": {
                    "type": "object",
                    "properties": {"call_id": {"type": "string"}},
                    "required": ["call_id"],
                },
            },
        ]
    }


def _create_phone_call(params: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "from_number": params.get("from_number"),
        "to_number": params.get("to_number"),
        "override_agent_id": params.get("override_agent_id"),
        "retell_llm_dynamic_variables": params.get("retell_llm_dynamic_variables") or {},
    }
    resp = requests.post(
        f"{_retell_base()}/v2/create-phone-call",
        headers=_retell_headers(),
        data=json.dumps(payload),
        timeout=60,
    )
    resp.raise_for_status()
    return {"data": resp.json()}


def _get_call(params: Dict[str, Any]) -> Dict[str, Any]:
    call_id = params.get("call_id")
    if not call_id:
        raise RuntimeError("call_id is required")
    resp = requests.get(
        f"{_retell_base()}/v2/get-call/{call_id}",
        headers=_retell_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return {"data": resp.json()}


def _create_web_call(params: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "agent_id": params.get("agent_id"),
        "retell_llm_dynamic_variables": params.get("retell_llm_dynamic_variables") or {},
    }
    resp = requests.post(
        f"{_retell_base()}/v2/create-web-call",
        headers=_retell_headers(),
        data=json.dumps(payload),
        timeout=60,
    )
    resp.raise_for_status()
    return {"data": resp.json()}


class MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/mcp":
            _json_response(self, {"error": "not_found"}, status=404)
            return
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            _json_response(self, {"error": "invalid_json"}, status=400)
            return

        method = body.get("method")
        if method == "tools/list":
            _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "result": _mcp_tools_list()})
            return

        if method == "tools/call":
            params = body.get("params", {})
            tool = params.get("name")
            args = params.get("arguments", {})
            try:
                if tool == "retell.create_phone_call":
                    result = _create_phone_call(args)
                elif tool == "retell.create_web_call":
                    result = _create_web_call(args)
                elif tool == "retell.get_call":
                    result = _get_call(args)
                else:
                    raise RuntimeError("unknown_tool")
                _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "result": result})
                return
            except Exception as exc:  # pylint: disable=broad-except
                _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"message": str(exc)}})
                return

        _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"message": "unknown_method"}})


def main() -> None:
    port = int(os.environ.get("RETELL_MCP_PORT", "7083"))
    server = HTTPServer(("0.0.0.0", port), MCPHandler)
    print(f"retell_mcp listening on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
