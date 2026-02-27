from __future__ import annotations

from typing import List

from ..schemas import Finding


def analyze(ctx) -> List[Finding]:
    delta = {
        "head_sha": ctx.snapshot.head_sha,
        "dirty_lines": len([line for line in ctx.snapshot.dirty_status.splitlines() if line.strip()]),
        "recent_commit_count": len(ctx.snapshot.recent_commits),
        "recent_commits": ctx.snapshot.recent_commits[:10],
    }
    ctx.report_sections["repo_delta"] = delta
    return []
