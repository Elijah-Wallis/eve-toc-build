from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src.runtime.proactive_review.daily_review import main


def _init_repo(path: Path) -> Path:
    repo = path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text("# Elijah_EveBot\n", encoding="utf-8")
    (repo / ".dockerignore").write_text("generated/\n", encoding="utf-8")
    (repo / "supabase").mkdir(parents=True, exist_ok=True)
    (repo / "supabase" / "schema.sql").write_text("-- schema\n", encoding="utf-8")
    (repo / "supabase" / "upgrade_001.sql").write_text("-- upgrade\n", encoding="utf-8")
    (repo / "src" / "runtime").mkdir(parents=True, exist_ok=True)
    runtime_file = repo / "src" / "runtime" / "__init__.py"
    runtime_file.write_text("__all__ = []\n", encoding="utf-8")

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, text=True)

    # Dirty runtime file to trigger gate_coverage finding.
    runtime_file.write_text("__all__ = []\n# dirty runtime\n", encoding="utf-8")
    return repo


def test_gate_coverage_proposal_is_validate_only(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    state_dir = tmp_path / "state"
    monkeypatch.setenv("REPO_ROOT", str(repo))
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(state_dir))

    rc = main(["--mode", "offline", "--profile", "fast", "--once"])
    assert rc == 0

    latest_report = json.loads((state_dir / "reports" / "daily" / "LATEST_REPORT.json").read_text(encoding="utf-8"))
    top = latest_report.get("top_proposals") or []
    gate = next(item for item in top if item.get("category") == "gate_coverage")
    assert gate["proposal_kind"] == "validate_only"
    assert gate["execution_commands"] == [
        "python3 scripts/acceptance/run_acceptance.py --ids AT-001,AT-002,AT-003,AT-007,AT-009,AT-011,AT-012"
    ]

    latest_dir = state_dir / "proposals" / "LATEST"
    proposal_dirs = [p for p in latest_dir.iterdir() if p.is_dir()]
    assert proposal_dirs
    gate_dir = next(p for p in proposal_dirs if "gate-coverage-runtime-dirty" in p.name)

    meta = json.loads((gate_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["proposal_kind"] == "validate_only"
    assert meta["execution_commands"] == [
        "python3 scripts/acceptance/run_acceptance.py --ids AT-001,AT-002,AT-003,AT-007,AT-009,AT-011,AT-012"
    ]
    assert not (gate_dir / "change.patch").exists()
    assert not (gate_dir / "apply.sh").exists()
