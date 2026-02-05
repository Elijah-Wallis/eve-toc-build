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


def _mcp_tools_list() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "supabase.request",
                "description": "Supabase REST request wrapper",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "method": {"type": "string"},
                        "path": {"type": "string"},
                        "query": {"type": "string"},
                        "json": {"type": "object"},
                        "headers": {"type": "object"},
                    },
                    "required": ["method", "path"],
                },
            }
        ]
    }


def _request(params: Dict[str, Any]) -> Dict[str, Any]:
    base = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not base or not key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")

    method = params.get("method", "GET").upper()
    path = params.get("path", "/")
    query = params.get("query", "")
    url = f"{base.rstrip('/')}{path}{query}"

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    extra = params.get("headers") or {}
    headers.update(extra)

    resp = requests.request(method, url, headers=headers, json=params.get("json"), timeout=60)
    resp.raise_for_status()
    try:
        return {"data": resp.json()}
    except ValueError:
        return {"text": resp.text}


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
                if tool == "supabase.request":
                    result = _request(args)
                else:
                    raise RuntimeError("unknown_tool")
                _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "result": result})
                return
            except Exception as exc:
                _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"message": str(exc)}})
                return

        _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"message": "unknown_method"}})


def main() -> None:
    port = int(os.environ.get("SUPABASE_MCP_PORT", "7082"))
    server = HTTPServer(("0.0.0.0", port), MCPHandler)
    print(f"supabase_mcp listening on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
