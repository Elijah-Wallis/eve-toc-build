from __future__ import annotations

import shutil
from typing import List

from ..schemas import Finding


def analyze(ctx) -> List[Finding]:
    findings: List[Finding] = []
    if shutil.which("ruff") is None:
        ctx.add_skipped("code_quality", "ruff_not_installed")
        return findings
    result = ctx.run_cmd("ruff check src/runtime/proactive_review", timeout=60)
    if result["status"] == "blocked":
        ctx.add_skipped("code_quality", "command_blocked")
        return findings
    if result["returncode"] != 0:
        findings.append(
            Finding(
                finding_id="code-quality-ruff",
                title="Ruff found style/lint issues in proactive module",
                category="code_quality",
                severity="low",
                summary="Ruff reported lint findings.",
                evidence=result["stdout"].splitlines()[:8],
                files=["src/runtime/proactive_review"],
                suggestion="Fix lint issues and re-run ruff check.",
            )
        )
    return findings
