from __future__ import annotations

from typing import Any, Dict, Optional

from .session_vault import SessionVault

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class OmegaHttpClient:
    """HTTP client that reads SessionVault on every request."""

    def __init__(self, vault: SessionVault) -> None:
        self.vault = vault

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        session_profile: str = "default",
        timeout: int = 30,
    ) -> Dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests is required for OmegaHttpClient")

        merged = {}
        merged.update(self.vault.get_headers(session_profile))
        if headers:
            merged.update(headers)

        resp = requests.request(
            method=method,
            url=url,
            headers=merged,
            params=params,
            json=json_body,
            timeout=timeout,
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return {"text": resp.text}
