from __future__ import annotations

from pathlib import Path
import pytest

from src.runtime.runtime_paths import repo_path
from src.runtime.runtime_paths import resolve_proposals_dir
from src.runtime.runtime_paths import resolve_repo_root
from src.runtime.runtime_paths import resolve_reports_dir
from src.runtime.runtime_paths import resolve_state_dir


def test_resolve_repo_root_points_to_repo() -> None:
    root = resolve_repo_root()
    assert root.exists()
    assert (root / "openclaw.json").exists()


def test_state_dir_resolves_to_absolute_path() -> None:
    state_dir = resolve_state_dir()
    assert isinstance(state_dir, Path)
    assert state_dir.is_absolute()


def test_repo_path_helper_is_root_relative() -> None:
    target = repo_path("src", "runtime")
    assert target.exists()


def test_reports_and_proposals_default_to_state_dir() -> None:
    reports = resolve_reports_dir()
    proposals = resolve_proposals_dir()
    state = resolve_state_dir()
    assert reports == state / "reports"
    assert proposals == state / "proposals"


def test_repo_local_report_override_requires_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    root = resolve_repo_root()
    monkeypatch.setenv("OPENCLAW_REPORTS_DIR", str(root / "reports"))
    monkeypatch.delenv("OPENCLAW_ALLOW_REPO_ARTIFACTS", raising=False)
    with pytest.raises(RuntimeError):
        resolve_reports_dir()
