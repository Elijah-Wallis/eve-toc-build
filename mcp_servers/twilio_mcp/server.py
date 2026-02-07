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


def _twilio_auth() -> tuple[str, str]:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        raise RuntimeError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN are required")
    return sid, token


def _twilio_base() -> str:
    sid, _ = _twilio_auth()
    return f"https://api.twilio.com/2010-04-01/Accounts/{sid}"


def _mcp_tools_list() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "twilio.send_sms",
                "description": "Send outbound SMS via Twilio",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string"},
                        "from": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["to", "from", "body"],
                },
            },
            {
                "name": "twilio.create_call",
                "description": "Create outbound Twilio voice call",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string"},
                        "from": {"type": "string"},
                        "twiml": {"type": "string"},
                    },
                    "required": ["to", "from", "twiml"],
                },
            },
        ]
    }


def _send_sms(params: Dict[str, Any]) -> Dict[str, Any]:
    sid, token = _twilio_auth()
    payload = {"To": params.get("to"), "From": params.get("from"), "Body": params.get("body")}
    resp = requests.post(
        f"{_twilio_base()}/Messages.json",
        auth=(sid, token),
        data=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return {"data": resp.json()}


def _create_call(params: Dict[str, Any]) -> Dict[str, Any]:
    sid, token = _twilio_auth()
    payload = {"To": params.get("to"), "From": params.get("from"), "Twiml": params.get("twiml")}
    resp = requests.post(
        f"{_twilio_base()}/Calls.json",
        auth=(sid, token),
        data=payload,
        timeout=30,
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
                if tool == "twilio.send_sms":
                    result = _send_sms(args)
                elif tool == "twilio.create_call":
                    result = _create_call(args)
                else:
                    raise RuntimeError("unknown_tool")
                _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "result": result})
                return
            except Exception as exc:  # pylint: disable=broad-except
                _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"message": str(exc)}})
                return

        _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"message": "unknown_method"}})


def main() -> None:
    port = int(os.environ.get("TWILIO_MCP_PORT", "7084"))
    server = HTTPServer(("0.0.0.0", port), MCPHandler)
    print(f"twilio_mcp listening on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
