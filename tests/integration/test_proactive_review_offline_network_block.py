from __future__ import annotations

import subprocess
from pathlib import Path

from src.runtime.proactive_review.daily_review import ReviewContext


def _init_repo(path: Path) -> Path:
    repo = path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text("# docs\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, text=True)
    return repo


def test_offline_network_command_is_denied(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    ctx = ReviewContext(repo_root=repo, mode="offline", profile="fast")
    result = ctx.run_cmd("curl https://example.com")
    assert result["status"] == "blocked"
    assert ctx.blocked_actions
