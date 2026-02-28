from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src.runtime.proactive_review.daily_review import main


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


def test_heartbeat_includes_required_fields(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    state_dir = tmp_path / "state"
    monkeypatch.setenv("REPO_ROOT", str(repo))
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(state_dir))

    rc = main(["--mode", "offline", "--profile", "fast", "--once"])
    assert rc == 0

    heartbeat_path = state_dir / "heartbeat" / "elijah_evebot_heartbeat.json"
    payload = json.loads(heartbeat_path.read_text(encoding="utf-8"))

    assert payload["agent"] == "Elijah_EveBot"
    assert isinstance(payload["blocked_actions"], list)
    assert isinstance(payload["skipped_checks"], list)
    assert isinstance(payload["proposal_counts_by_tier"], dict)
    assert isinstance(payload["proposal_counts_by_category"], dict)
    assert "latest_report_markdown" in payload["pointers"]
    assert "latest_proposals" in payload["pointers"]
