from __future__ import annotations

from typing import List

from ..schemas import Finding


def analyze(ctx) -> List[Finding]:
    findings: List[Finding] = []
    readme = (ctx.repo_root / "README.md")
    if not readme.exists():
        return findings
    text = readme.read_text(encoding="utf-8", errors="ignore")
    if "Elijah_EveBot" not in text:
        findings.append(
            Finding(
                finding_id="docs-drift-missing-proactive-loop",
                title="README missing proactive loop runbook",
                category="docs_drift",
                severity="low",
                summary="README does not document Elijah_EveBot daily workflow.",
                files=["README.md"],
                suggestion="Add a concise section with run once + launchd install commands.",
            )
        )
    return findings
