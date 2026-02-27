from __future__ import annotations

import fcntl
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


def test_lock_contention_records_warning_and_skip(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    state_dir = tmp_path / "state"
    lock_path = state_dir / "locks" / "elijah_evebot.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("REPO_ROOT", str(repo))
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(state_dir))

    with lock_path.open("a+") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        rc = main(["--mode", "offline", "--profile", "fast", "--once"])
        assert rc == 0

    heartbeat = json.loads((state_dir / "heartbeat" / "elijah_evebot_heartbeat.json").read_text(encoding="utf-8"))
    assert heartbeat["status"] == "warning"
    assert {"check": "run_lock", "reason": "skipped_run_lock_held"} in heartbeat["skipped_checks"]
