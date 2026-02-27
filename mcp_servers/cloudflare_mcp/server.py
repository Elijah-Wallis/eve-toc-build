from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

import requests

_ENV_LOADED = False


def _json_response(handler: BaseHTTPRequestHandler, payload: Dict[str, Any], status: int = 200) -> None:
    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _cf_token() -> str:
    _load_cloudflare_env()
    token = (
        os.environ.get("CLOUDFLARE_API_TOKEN")
        or os.environ.get("CF_API_TOKEN")
        or os.environ.get("CLOUDFLARE_TOKEN")
        or ""
    ).strip()
    if not token:
        raise RuntimeError("CLOUDFLARE_API_TOKEN is required")
    return token


def _cf_base() -> str:
    return "https://api.cloudflare.com/client/v4"


def _cf_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {_cf_token()}", "Content-Type": "application/json"}


def _cf_request(method: str, path: str, *, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{_cf_base()}{path}"
    resp = requests.request(
        method=method.upper(),
        url=url,
        headers=_cf_headers(),
        params=params or None,
        data=json.dumps(body) if body is not None else None,
        timeout=60,
    )
    data = resp.json() if resp.content else {}
    if resp.status_code >= 400 or not data.get("success", False):
        raise RuntimeError(
            f"cloudflare_api_error status={resp.status_code} errors={data.get('errors')} messages={data.get('messages')}"
        )
    return data


def _resolve_account_id(params: Dict[str, Any]) -> str:
    _load_cloudflare_env()
    account_id = str(params.get("account_id") or os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("CF_ACCOUNT_ID") or "").strip()
    if not account_id:
        raise RuntimeError("account_id is required (or set CLOUDFLARE_ACCOUNT_ID)")
    return account_id


def _resolve_zone_id(params: Dict[str, Any]) -> str:
    _load_cloudflare_env()
    zone_id = str(params.get("zone_id") or os.environ.get("CLOUDFLARE_ZONE_ID") or os.environ.get("CF_ZONE_ID") or "").strip()
    if zone_id:
        return zone_id

    hostname = str(params.get("hostname") or "").strip().lower()
    zone_name = str(params.get("zone_name") or "").strip().lower()
    if hostname and not zone_name:
        parts = hostname.split(".")
        if len(parts) >= 2:
            zone_name = ".".join(parts[-2:])
    if not zone_name:
        raise RuntimeError("zone_id is required (or set CLOUDFLARE_ZONE_ID / provide zone_name / hostname)")

    data = _cf_request("GET", "/zones", params={"name": zone_name, "status": "active", "per_page": 1})
    rows = data.get("result") or []
    if not rows:
        raise RuntimeError(f"zone_not_found name={zone_name}")
    return str(rows[0]["id"])


def _mcp_tools_list() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "cloudflare.verify_token",
                "description": "Verify Cloudflare API token and scopes.",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "cloudflare.list_zones",
                "description": "List accessible DNS zones.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "status": {"type": "string"},
                        "per_page": {"type": "number"},
                    },
                    "required": [],
                },
            },
            {
                "name": "cloudflare.list_tunnels",
                "description": "List Cloudflare tunnels for account.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"account_id": {"type": "string"}},
                    "required": [],
                },
            },
            {
                "name": "cloudflare.create_tunnel",
                "description": "Create named Cloudflare tunnel.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string"},
                        "name": {"type": "string"},
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "cloudflare.create_tunnel_token",
                "description": "Create run token for an existing tunnel.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string"},
                        "tunnel_id": {"type": "string"},
                    },
                    "required": ["tunnel_id"],
                },
            },
            {
                "name": "cloudflare.upsert_dns_cname",
                "description": "Upsert DNS CNAME record for tunnel hostname.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "zone_id": {"type": "string"},
                        "zone_name": {"type": "string"},
                        "hostname": {"type": "string"},
                        "target": {"type": "string"},
                        "proxied": {"type": "boolean"},
                    },
                    "required": ["hostname", "target"],
                },
            },
        ]
    }


def _verify_token(_: Dict[str, Any]) -> Dict[str, Any]:
    data = _cf_request("GET", "/user/tokens/verify")
    return {"data": data.get("result")}


def _list_zones(params: Dict[str, Any]) -> Dict[str, Any]:
    query = {
        "status": str(params.get("status") or "active"),
        "per_page": str(int(params.get("per_page") or 50)),
    }
    if params.get("name"):
        query["name"] = str(params["name"])
    data = _cf_request("GET", "/zones", params=query)
    rows = data.get("result") or []
    slim = [
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "status": row.get("status"),
            "account_id": (row.get("account") or {}).get("id"),
        }
        for row in rows
    ]
    return {"data": slim}


def _list_tunnels(params: Dict[str, Any]) -> Dict[str, Any]:
    account_id = _resolve_account_id(params)
    data = _cf_request("GET", f"/accounts/{account_id}/cfd_tunnel", params={"is_deleted": "false", "per_page": 100})
    rows = data.get("result") or []
    slim = [
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "status": row.get("status"),
            "created_at": row.get("created_at"),
        }
        for row in rows
    ]
    return {"data": slim}


def _create_tunnel(params: Dict[str, Any]) -> Dict[str, Any]:
    account_id = _resolve_account_id(params)
    name = str(params.get("name") or "").strip()
    if not name:
        raise RuntimeError("name is required")
    data = _cf_request("POST", f"/accounts/{account_id}/cfd_tunnel", body={"name": name, "config_src": "cloudflare"})
    row = data.get("result") or {}
    return {
        "data": {
            "id": row.get("id"),
            "name": row.get("name"),
            "status": row.get("status"),
            "created_at": row.get("created_at"),
        }
    }


def _create_tunnel_token(params: Dict[str, Any]) -> Dict[str, Any]:
    account_id = _resolve_account_id(params)
    tunnel_id = str(params.get("tunnel_id") or "").strip()
    if not tunnel_id:
        raise RuntimeError("tunnel_id is required")
    data = _cf_request("GET", f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/token")
    row = data.get("result") or {}
    return {"data": {"token": row.get("token"), "tunnel_id": tunnel_id}}


def _upsert_dns_cname(params: Dict[str, Any]) -> Dict[str, Any]:
    hostname = str(params.get("hostname") or "").strip().lower()
    target = str(params.get("target") or "").strip().rstrip(".")
    proxied = bool(params.get("proxied", True))
    if not hostname or not target:
        raise RuntimeError("hostname and target are required")

    zone_id = _resolve_zone_id(params)

    lookup = _cf_request(
        "GET",
        f"/zones/{zone_id}/dns_records",
        params={"type": "CNAME", "name": hostname, "per_page": 1},
    )
    rows = lookup.get("result") or []
    body = {"type": "CNAME", "name": hostname, "content": target, "ttl": 1, "proxied": proxied}
    if rows:
        rec_id = rows[0]["id"]
        data = _cf_request("PUT", f"/zones/{zone_id}/dns_records/{rec_id}", body=body)
        action = "updated"
    else:
        data = _cf_request("POST", f"/zones/{zone_id}/dns_records", body=body)
        action = "created"
    row = data.get("result") or {}
    return {
        "data": {
            "action": action,
            "id": row.get("id"),
            "name": row.get("name"),
            "type": row.get("type"),
            "content": row.get("content"),
            "proxied": row.get("proxied"),
        }
    }


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
                if tool == "cloudflare.verify_token":
                    result = _verify_token(args)
                elif tool == "cloudflare.list_zones":
                    result = _list_zones(args)
                elif tool == "cloudflare.list_tunnels":
                    result = _list_tunnels(args)
                elif tool == "cloudflare.create_tunnel":
                    result = _create_tunnel(args)
                elif tool == "cloudflare.create_tunnel_token":
                    result = _create_tunnel_token(args)
                elif tool == "cloudflare.upsert_dns_cname":
                    result = _upsert_dns_cname(args)
                else:
                    raise RuntimeError("unknown_tool")
                _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "result": result})
                return
            except Exception as exc:  # pylint: disable=broad-except
                _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"message": str(exc)}})
                return

        _json_response(self, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"message": "unknown_method"}})


def main() -> None:
    _load_cloudflare_env()
    port = int(os.environ.get("CLOUDFLARE_MCP_PORT", "7086"))
    server = HTTPServer(("0.0.0.0", port), MCPHandler)
    print(f"cloudflare_mcp listening on :{port}")
    server.serve_forever()


def _load_cloudflare_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    path = os.environ.get("CLOUDFLARE_ENV_FILE", "~/.openclaw-eve/cloudflare.env")
    env_path = Path(path).expanduser()
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            row = line.strip()
            if not row or row.startswith("#") or "=" not in row:
                continue
            key, value = row.split("=", 1)
            key = key.strip()
            if key and value is not None and key not in os.environ:
                os.environ[key] = value.strip()
    _ENV_LOADED = True


if __name__ == "__main__":
    main()
