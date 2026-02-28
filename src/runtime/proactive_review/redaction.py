from __future__ import annotations

import re
from typing import Any, Dict, Iterable

_REPLACEMENT = "[REDACTED]"

_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._\-+/=]{8,}", re.IGNORECASE),
    re.compile(r"(SUPABASE_SERVICE_ROLE_KEY|API_KEY|TOKEN|SECRET)\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{8,}['\"]?", re.IGNORECASE),
    re.compile(r"[A-Za-z0-9._%+-]+:[^\s@]+@[^\s/]+"),
    re.compile(r"https?://[^\s]+:[^\s]+@[^\s]+"),
]

_SENSITIVE_KEYS = {
    "supabase_service_role_key",
    "api_key",
    "token",
    "secret",
    "authorization",
    "bearer",
}


def redact_text(value: str) -> str:
    out = value
    for pattern in _PATTERNS:
        out = pattern.sub(_REPLACEMENT, out)
    return out


def redact_obj(value: Any) -> Any:
    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                result[key] = _REPLACEMENT
            else:
                result[key] = redact_obj(item)
        return result
    if isinstance(value, list):
        return [redact_obj(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def env_presence(keys: Iterable[str], env: Dict[str, str]) -> Dict[str, str]:
    return {key: ("present" if str(env.get(key, "")).strip() else "missing") for key in keys}
