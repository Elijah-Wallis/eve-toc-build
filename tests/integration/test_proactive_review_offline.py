from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src.runtime.proactive_review.daily_review import main


def _init_repo(path: Path) -> Path:
    repo = path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text("# sample\n", encoding="utf-8")
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, text=True)
    return repo


def test_offline_run_writes_dated_and_latest_and_latest_proposals(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    state_dir = tmp_path / "state"
    monkeypatch.setenv("REPO_ROOT", str(repo))
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(state_dir))

    rc = main(["--mode", "offline", "--profile", "fast", "--once"])
    assert rc == 0

    daily_dir = state_dir / "reports" / "daily"
    files = sorted(daily_dir.glob("*_report.md"))
    assert files, "expected dated report markdown"

    latest_md = daily_dir / "LATEST_REPORT.md"
    latest_json = daily_dir / "LATEST_REPORT.json"
    assert latest_md.exists()
    assert latest_json.exists()
    payload = json.loads(latest_json.read_text(encoding="utf-8"))
    assert payload.get("repo_commit")
    assert payload.get("repo", {}).get("pre_head") == payload.get("repo_commit")

    proposals_latest = state_dir / "proposals" / "LATEST"
    assert proposals_latest.exists()
    assert proposals_latest.is_dir()
    latest_children = [p for p in proposals_latest.iterdir() if p.is_dir()]
    assert latest_children, "expected per-run proposal directories"


def test_offline_run_keeps_per_run_proposal_history(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    state_dir = tmp_path / "state"
    monkeypatch.setenv("REPO_ROOT", str(repo))
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(state_dir))

    rc_first = main(["--mode", "offline", "--profile", "fast", "--once"])
    rc_second = main(["--mode", "offline", "--profile", "fast", "--once"])
    assert rc_first == 0
    assert rc_second == 0

    dated_dirs = [p for p in (state_dir / "proposals").iterdir() if p.is_dir() and p.name != "LATEST"]
    assert dated_dirs, "expected dated proposal directories"
    run_dirs = [p for p in dated_dirs[0].iterdir() if p.is_dir()]
    assert len(run_dirs) >= 2
