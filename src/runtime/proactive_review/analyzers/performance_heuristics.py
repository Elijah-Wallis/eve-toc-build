from __future__ import annotations

from typing import List

from ..schemas import Finding


def analyze(ctx) -> List[Finding]:
    findings: List[Finding] = []
    cmd = "rg -n --hidden --no-ignore-vcs '\\[[^\\]]+\\]\\[[^\\]]+\\]\\[[^\\]]+\\]' src scripts --glob '*.py'"
    deep_lookup = ctx.run_cmd(cmd, timeout=60)
    rows = [line for line in deep_lookup["stdout"].splitlines() if line.strip()]
    if rows:
        findings.append(
            Finding(
                finding_id="perf-heuristic-deep-indexing",
                title="Deep indexing pattern found in Python hot paths",
                category="performance_heuristics",
                severity="low",
                summary="Nested indexing can indicate pointer-chasing in tight loops.",
                evidence=rows[:5],
                suggestion="Cache intermediate objects or compile lookups to ids/offsets in hot paths.",
            )
        )
    return findings
