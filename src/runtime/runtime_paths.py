from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional


def _git_repo_root(cwd: Path) -> Optional[Path]:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except Exception:  # pragma: no cover
        return None
    if proc.returncode != 0:
        return None
    root = (proc.stdout or "").strip()
    if not root:
        return None
    path = Path(root).resolve()
    return path if path.exists() else None


def resolve_repo_root() -> Path:
    env_root = str(os.environ.get("REPO_ROOT", "")).strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    cwd = Path.cwd().resolve()
    git_root = _git_repo_root(cwd)
    return git_root if git_root is not None else cwd


def resolve_state_dir() -> Path:
    configured = str(os.environ.get("OPENCLAW_STATE_DIR", "")).strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".openclaw-eve").resolve()


def repo_path(*parts: str) -> Path:
    return resolve_repo_root().joinpath(*parts).resolve()


def state_path(*parts: str) -> Path:
    return resolve_state_dir().joinpath(*parts).resolve()


def resolve_generated_dir() -> Path:
    override = str(os.environ.get("EVE_GENERATED_DIR", "")).strip()
    target = Path(override).expanduser().resolve() if override else state_path("generated")
    repo_generated = repo_path("generated")
    allow_repo_generated = str(os.environ.get("OPENCLAW_ALLOW_REPO_GENERATED", "")).strip() == "1"
    if (target == repo_generated or repo_generated in target.parents) and not allow_repo_generated:
        raise RuntimeError(
            "repo-local generated output is disabled; set OPENCLAW_ALLOW_REPO_GENERATED=1 to opt in explicitly"
        )
    return target
