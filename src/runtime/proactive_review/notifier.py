from __future__ import annotations

from pathlib import Path


def write_local_notice(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(message, encoding="utf-8")
