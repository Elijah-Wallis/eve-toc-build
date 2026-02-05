from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class SessionProfile:
    storage_state_path: Optional[str] = None
    bearer_token: Optional[str] = None


class SessionVault:
    """Dynamic session store (Playwright storage_state.json or bearer tokens).

    File format:
    {
      "version": 1,
      "profiles": {
        "default": {
          "storage_state_path": "/path/to/storage_state.json",
          "bearer_token": "..."
        }
      }
    }
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def _load_raw(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "profiles": {}}
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def load_profile(self, name: str = "default") -> SessionProfile:
        raw = self._load_raw()
        profiles = raw.get("profiles", {})
        data = profiles.get(name, {})
        return SessionProfile(
            storage_state_path=data.get("storage_state_path"),
            bearer_token=data.get("bearer_token"),
        )

    @staticmethod
    def _cookie_header_from_storage_state(storage_state_path: str) -> str:
        path = Path(storage_state_path)
        if not path.exists():
            return ""
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        cookies = data.get("cookies", [])
        pairs = []
        for c in cookies:
            name = c.get("name")
            value = c.get("value")
            if name and value is not None:
                pairs.append(f"{name}={value}")
        return "; ".join(pairs)

    def get_headers(self, profile: str = "default") -> Dict[str, str]:
        # Load on every request to honor Session Leech requirement
        p = self.load_profile(profile)
        headers: Dict[str, str] = {}
        if p.bearer_token:
            headers["Authorization"] = f"Bearer {p.bearer_token}"
        if p.storage_state_path:
            cookie_header = self._cookie_header_from_storage_state(p.storage_state_path)
            if cookie_header:
                headers["Cookie"] = cookie_header
        return headers
