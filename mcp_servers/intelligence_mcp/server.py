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


def _ontology() -> OntologyClient:
    return OntologyClient(actor="intelligence-mcp")


def _tool_list() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "intelligence.lead_snapshot",
                "description": "Fetch one PatientJourney snapshot by lead_id or phone through the ontology boundary.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"lead_id": {"type": "string"}, "phone": {"type": "string"}},
                    "required": [],
                },
            },
            {
                "name": "intelligence.recent_events",
                "description": "Fetch recent FinancialEvent records by lead_id through the ontology boundary.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"lead_id": {"type": "string"}, "limit": {"type": "number"}},
                    "required": ["lead_id"],
                },
            },
        ]
    }


def _lead_snapshot(params: Dict[str, Any]) -> Dict[str, Any]:
    lead_id = str(params.get("lead_id") or "").strip()
    phone = str(params.get("phone") or "").strip()
    if not lead_id and not phone:
        raise RuntimeError("lead_id or phone is required")
    return {"data": _ontology().get_patient_journey(lead_id=lead_id, phone=phone)}


def _recent_events(params: Dict[str, Any]) -> Dict[str, Any]:
    lead_id = str(params.get("lead_id") or "").strip()
    if not lead_id:
        raise RuntimeError("lead_id is required")
    limit = max(1, min(int(params.get("limit", 25)), 200))
    return {"data": _ontology().list_recent_patient_journey_events(lead_id, limit)}


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
            _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "result": _tool_list()})
            return

        if method == "tools/call":
            params = body.get("params", {})
            tool = params.get("name")
            args = params.get("arguments", {})
            try:
                if tool == "intelligence.lead_snapshot":
                    result = _lead_snapshot(args)
                elif tool == "intelligence.recent_events":
                    result = _recent_events(args)
                else:
                    raise RuntimeError("unknown_tool")
                _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "result": result})
                return
            except Exception as exc:  # noqa: BLE001
                _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"message": str(exc)}})
                return

        _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"message": "unknown_method"}})


def main() -> None:
    port = int(os.environ.get("INTELLIGENCE_MCP_PORT", "7085"))
    server = HTTPServer(("0.0.0.0", port), MCPHandler)
    print(f"intelligence_mcp listening on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
