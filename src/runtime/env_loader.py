from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .config_adapter import apply_env_aliases
from .http_traffic import install_requests_traffic_recorder
from .runtime_paths import resolve_state_dir
from .secrets_provider import SecretsProvider


def load_env_file(path: Optional[str] = None) -> None:
    if path:
        target = Path(path).expanduser().resolve()
    else:
        state_dir = resolve_state_dir()
        target = (state_dir.parent / ".openclaw_env").resolve()
    if not target.exists():
        _post_load_setup()
        return
    for line in target.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"')
        if key and key not in os.environ:
            os.environ[key] = value
    _post_load_setup()


def _post_load_setup() -> None:
    apply_env_aliases()
    SecretsProvider().install_defaults()
    if os.environ.get("OPENCLAW_CAPTURE_TRAFFIC", "1") != "0":
        install_requests_traffic_recorder()
