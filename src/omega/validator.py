from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from .http_client import OmegaHttpClient
from .session_vault import SessionVault

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


class ValidationError(RuntimeError):
    pass


def _shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _shape(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        if not value:
            return []
        return [_shape(value[0])]
    return type(value).__name__


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_openapi(path: str) -> Dict[str, Any]:
    if yaml is None:
        raise ValidationError("PyYAML is required to parse openapi.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _openapi_has_path(openapi: Dict[str, Any], url: str) -> bool:
    paths = openapi.get("paths", {})
    for p in paths.keys():
        if p in url:
            return True
    return False


@dataclass
class OmegaValidator:
    openapi_path: str
    test_event_path: str
    session_vault_path: str

    def validate(self) -> None:
        openapi = _load_openapi(self.openapi_path)
        test_event = _load_json(self.test_event_path)

        url = test_event["url"]
        method = test_event.get("method", "GET")
        headers = test_event.get("headers")
        params = test_event.get("params")
        json_body = test_event.get("json_body")
        session_profile = test_event.get("session_profile", "default")

        if not _openapi_has_path(openapi, url):
            raise ValidationError("OpenAPI does not contain target path")

        vault = SessionVault(self.session_vault_path)
        client = OmegaHttpClient(vault)
        response = client.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json_body=json_body,
            session_profile=session_profile,
        )

        actual_shape = _shape(response)
        if "expected_response_shape" in test_event:
            expected_shape = test_event["expected_response_shape"]
        elif "expected_response_path" in test_event:
            expected_shape = _shape(_load_json(test_event["expected_response_path"]))
        else:
            raise ValidationError("test_event missing expected_response_shape/expected_response_path")

        if actual_shape != expected_shape:
            raise ValidationError("Response shape drift detected")
