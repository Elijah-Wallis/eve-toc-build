from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlsplit

import requests

_LOCK = threading.Lock()
_INSTALLED = False
_ORIGINAL_REQUEST = None

_SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "supabase_service_role_key",
    "twilio_auth_token",
}

_SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"^Bearer\s+[A-Za-z0-9._\-]{16,}$", re.IGNORECASE),
    re.compile(r"^eyJ[A-Za-z0-9._\-]{20,}$"),  # JWT-like values
    re.compile(r"^[A-Za-z0-9_\-]{24,}$"),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _looks_sensitive_string(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    return any(pattern.match(text) for pattern in _SENSITIVE_VALUE_PATTERNS)


def _sanitize_payload(value: Any, key_hint: str = "") -> Any:
    key_l = key_hint.lower()
    if key_l in _SENSITIVE_KEYS:
        return "<redacted>"
    if isinstance(value, dict):
        return {str(k): _sanitize_payload(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_payload(v, key_hint) for v in value]
    if isinstance(value, str):
        return "<redacted>" if _looks_sensitive_string(value) else value
    return value


def _headers_summary(headers: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(headers, dict):
        return {}
    out: Dict[str, Any] = {}
    for key, value in headers.items():
        key_s = str(key)
        value_s = str(value)
        out[key_s] = "<redacted>" if key_s.lower() in _SENSITIVE_KEYS or _looks_sensitive_string(value_s) else value_s
    return out


def install_requests_traffic_recorder(path: Optional[str] = None) -> None:
    global _INSTALLED, _ORIGINAL_REQUEST  # pylint: disable=global-statement
    with _LOCK:
        if _INSTALLED:
            return

        target = Path(os.path.expanduser(path or os.environ.get("OPENCLAW_API_TRAFFIC_FILE", "~/.openclaw-eve/runtime/api_traffic.jsonl")))
        target.parent.mkdir(parents=True, exist_ok=True)

        _ORIGINAL_REQUEST = requests.sessions.Session.request

        def _wrapped_request(self: requests.sessions.Session, method: str, url: str, **kwargs: Any) -> requests.Response:
            started = time.time()
            response = None
            error_text = None
            try:
                response = _ORIGINAL_REQUEST(self, method, url, **kwargs)
                return response
            except Exception as exc:  # pylint: disable=broad-except
                error_text = str(exc)
                raise
            finally:
                parsed = urlsplit(url)
                request_params = kwargs.get("params")
                query_map: Dict[str, Any]
                if isinstance(request_params, dict):
                    query_map = {str(k): _sanitize_payload(v, str(k)) for k, v in request_params.items()}
                else:
                    parsed_query = parse_qs(parsed.query, keep_blank_values=True)
                    query_map = {k: (_sanitize_payload(v[0], k) if len(v) == 1 else _sanitize_payload(v, k)) for k, v in parsed_query.items()}

                request_json = kwargs.get("json")
                request_data = kwargs.get("data")
                if isinstance(request_data, (bytes, bytearray)):
                    request_data = "<binary>"
                elif request_data is not None and not isinstance(request_data, (dict, list, str, int, float, bool)):
                    request_data = str(type(request_data).__name__)

                record = {
                    "ts": _now_iso(),
                    "event": "http_traffic",
                    "method": str(method).upper(),
                    "url": url,
                    "scheme": parsed.scheme,
                    "host": parsed.netloc,
                    "path": parsed.path or "/",
                    "query": query_map,
                    "request": {
                        "headers": _headers_summary(kwargs.get("headers")),
                        "json": _sanitize_payload(request_json),
                        "data": _sanitize_payload(request_data),
                        "timeout": kwargs.get("timeout"),
                    },
                    "response": {
                        "status_code": response.status_code if response is not None else None,
                        "ok": bool(response.ok) if response is not None else False,
                    },
                    "duration_ms": int((time.time() - started) * 1000),
                }
                if response is not None:
                    content_type = response.headers.get("content-type", "")
                    record["response"]["content_type"] = content_type
                if error_text:
                    record["error"] = error_text
                with target.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=True) + "\n")

        requests.sessions.Session.request = _wrapped_request
        _INSTALLED = True

