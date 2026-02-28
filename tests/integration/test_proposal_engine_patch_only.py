from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from src.runtime.proactive_review.daily_review import main


def _init_repo(path: Path) -> Path:
    repo = path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text("# docs\n", encoding="utf-8")
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, text=True)
    return repo


def _status(repo: Path) -> str:
    return subprocess.run(["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True, check=True).stdout.strip()


def test_proposal_engine_emits_patch_with_meta_and_apply_script_without_repo_mutation(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    state_dir = tmp_path / "state"
    monkeypatch.setenv("REPO_ROOT", str(repo))
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(state_dir))

    pre = _status(repo)
    rc = main(["--mode", "offline", "--profile", "fast", "--once"])
    assert rc == 0
    post = _status(repo)
    assert pre == post

    latest = state_dir / "proposals" / "LATEST"
    proposal_dirs = [p for p in latest.iterdir() if p.is_dir()]
    assert proposal_dirs, "expected at least one proposal directory"

    proposal_dir = proposal_dirs[0]
    patch_text = (proposal_dir / "change.patch").read_text(encoding="utf-8")
    assert "diff --git" in patch_text
    assert re.search(r"^index [0-9a-f]{40}\.\.[0-9a-f]{40}", patch_text, flags=re.MULTILINE)

    meta = json.loads((proposal_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["base_sha"]
    assert meta["patch_apply_method"] == "git apply"

    apply_text = (proposal_dir / "apply.sh").read_text(encoding="utf-8")
    assert "git apply --check change.patch" in apply_text
    assert "git apply change.patch" in apply_text
