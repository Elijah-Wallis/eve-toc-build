from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .config_adapter import resolve_state_dir


class SecretsProvider:
    """File-first secret provider with opt-in env fallback."""

    def __init__(self) -> None:
        self.source = os.environ.get("OPENCLAW_SECRETS_SOURCE", "file").strip().lower()
        self.allow_env_fallback = os.environ.get("OPENCLAW_ALLOW_ENV_SECRET_FALLBACK", "0") == "1"
        state_dir = resolve_state_dir()
        self._default_files = {
            "OPENCLAW_TELEGRAM_BOT_TOKEN": state_dir / "credentials" / "telegram" / "token",
            "OPENCLAW_GATEWAY_TOKEN": state_dir / "credentials" / "gateway" / "token",
            "N8N_MCP_TOKEN": state_dir / "credentials" / "n8n" / "mcp_token",
            "N8N_API_KEY": state_dir / "credentials" / "n8n" / "api_key",
            "SUPABASE_SERVICE_ROLE_KEY": state_dir / "credentials" / "supabase" / "service_role_key",
        }

    def get(self, key: str, default: Optional[str] = None, *, allow_env_fallback: bool = False) -> Optional[str]:
        if self.source == "env":
            return os.environ.get(key, default)
        file_value = self._read_file_secret(key)
        if file_value:
            return file_value
        if allow_env_fallback or self.allow_env_fallback:
            env_value = os.environ.get(key)
            if env_value:
                return env_value
        return default

    def install_defaults(self) -> None:
        for key in self._default_files:
            if os.environ.get(key):
                continue
            value = self.get(key, allow_env_fallback=True)
            if value:
                os.environ[key] = value

    def _read_file_secret(self, key: str) -> Optional[str]:
        file_key = f"{key}_FILE"
        env_path = os.environ.get(file_key, "")
        if env_path:
            return _read_secret_file(Path(os.path.expanduser(env_path)))
        default_path = self._default_files.get(key)
        if not default_path:
            return None
        return _read_secret_file(default_path)


def _read_secret_file(path: Path) -> Optional[str]:
    try:
        if not path.exists():
            return None
        value = path.read_text(encoding="utf-8").strip()
        return value or None
    except OSError:
        return None
