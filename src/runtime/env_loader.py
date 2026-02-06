from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .http_traffic import install_requests_traffic_recorder


def load_env_file(path: Optional[str] = None) -> None:
    target = Path(os.path.expanduser(path or "~/.openclaw_env"))
    if not target.exists():
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

    if os.environ.get("OPENCLAW_CAPTURE_TRAFFIC", "1") != "0":
        install_requests_traffic_recorder()
