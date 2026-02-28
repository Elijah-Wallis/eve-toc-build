from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class RepoSnapshot:
    head_sha: str
    dirty_status: str
    tracked_files: List[str]
    recent_commits: List[Dict[str, str]]


class RepoIndexer:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def _run(self, args: List[str]) -> str:
        proc = subprocess.run(args, cwd=self.repo_root, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            return ""
        return (proc.stdout or "").strip()

    def build_snapshot(self) -> RepoSnapshot:
        head_sha = self._run(["git", "rev-parse", "HEAD"])
        dirty_status = self._run(["git", "status", "--porcelain"])
        tracked_files = [line.strip() for line in self._run(["git", "ls-files"]).splitlines() if line.strip()]
        recent_commits: List[Dict[str, str]] = []
        logs = self._run(["git", "log", "-n", "30", "--pretty=format:%H|%ct|%s"])
        for row in logs.splitlines():
            parts = row.split("|", 2)
            if len(parts) != 3:
                continue
            recent_commits.append({"sha": parts[0], "ts": parts[1], "subject": parts[2]})
        return RepoSnapshot(
            head_sha=head_sha,
            dirty_status=dirty_status,
            tracked_files=tracked_files,
            recent_commits=recent_commits,
        )

    @staticmethod
    def status_signature(status_text: str) -> str:
        return json.dumps(sorted(line for line in status_text.splitlines() if line.strip()))
