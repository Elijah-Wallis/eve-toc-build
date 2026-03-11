from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict

from ontology.client import OntologyClient


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
                "name": "ontology.request",
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
    method = params.get("method", "GET").upper()
    path = params.get("path", "/")
    query = params.get("query", "")
    payload = params.get("json")
    extra_headers = params.get("headers") or {}
    return OntologyClient().request(method, path, query=query, json_payload=payload, headers=extra_headers, timeout=60)


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
                if tool == "ontology.request":
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
