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
                "name": "apify.run_actor",
                "description": "Run Apify actor and return dataset items",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "actor_id": {"type": "string"},
                        "input": {"type": "object"},
                    },
                    "required": ["input"],
                },
            }
        ]
    }


def _run_actor(params: Dict[str, Any]) -> Dict[str, Any]:
    token = os.environ.get("APIFY_API_TOKEN")
    actor_id = params.get("actor_id") or os.environ.get("APIFY_ACTOR_ID", "compass/crawler-google-places")
    if not token:
        raise RuntimeError("APIFY_API_TOKEN is not set")

    url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items?token={token}&timeout=300&clean=true"
    resp = requests.post(url, json=params.get("input", {}), timeout=300)
    resp.raise_for_status()
    return {"items": resp.json()}


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
                if tool == "apify.run_actor":
                    result = _run_actor(args)
                else:
                    raise RuntimeError("unknown_tool")
                _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "result": result})
                return
            except Exception as exc:
                _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"message": str(exc)}})
                return

        _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"message": "unknown_method"}})


def main() -> None:
    port = int(os.environ.get("APIFY_MCP_PORT", "7081"))
    server = HTTPServer(("0.0.0.0", port), MCPHandler)
    print(f"apify_mcp listening on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
