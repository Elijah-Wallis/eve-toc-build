from __future__ import annotations

import json
import os
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
                "name": "ontology.query",
                "description": "Query ontology-backed objects through the canonical boundary.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_name": {"type": "string"},
                        "filters": {"type": "object"},
                        "select": {"type": "string"},
                        "limit": {"type": "number"},
                        "order": {"type": "string"},
                    },
                    "required": ["object_name"],
                },
            }
        ]
    }


def _ontology() -> OntologyClient:
    return OntologyClient(actor="ontology-mcp")


def _query(params: Dict[str, Any]) -> Dict[str, Any]:
    object_name = str(params.get("object_name") or "").strip()
    if not object_name:
        raise RuntimeError("object_name is required")
    filters = params.get("filters") or {}
    if not isinstance(filters, dict):
        raise RuntimeError("filters must be an object")
    select = str(params.get("select") or "*")
    limit = max(1, min(int(params.get("limit", 25)), 500))
    order = str(params.get("order") or "")
    data = _ontology().query_object(
        object_name=object_name,
        filters=filters,
        select=select,
        limit=limit,
        order=order,
    )
    return {"data": data}


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
                if tool == "ontology.query":
                    result = _query(args)
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
