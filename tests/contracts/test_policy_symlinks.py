from __future__ import annotations

import os
from pathlib import Path


def _assert_symlink_with_suffix(path: Path, suffix: str) -> None:
    assert path.exists() or path.is_symlink(), f"missing required path: {path}"
    assert path.is_symlink(), f"expected symlink (not a regular file): {path}"

    target = os.readlink(path)
    assert target.endswith(suffix), f"unexpected symlink target for {path}: {target!r}"


def test_workspace_template_policy_files_are_symlinks() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    template_dir = repo_root / "openclaw_workspace_template"

    _assert_symlink_with_suffix(template_dir / "SOUL.md", "/workspace/SOUL.md")
    _assert_symlink_with_suffix(template_dir / "HEARTBEAT.md", "/workspace/HEARTBEAT.md")

