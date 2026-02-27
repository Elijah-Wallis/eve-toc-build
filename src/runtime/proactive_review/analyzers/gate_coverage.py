from __future__ import annotations

from typing import List

from ..schemas import Finding


RUNTIME_GATES = ["AT-001", "AT-002", "AT-003", "AT-007", "AT-009", "AT-011", "AT-012", "AT-013B"]


def analyze(ctx) -> List[Finding]:
    findings: List[Finding] = []
    dirty_files: List[str] = []
    for raw in ctx.snapshot.dirty_status.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            continue
        path = parts[1].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path:
            dirty_files.append(path)
    touched_runtime = [path for path in dirty_files if path.startswith("src/runtime/")]
    if touched_runtime:
        findings.append(
            Finding(
                finding_id="gate-coverage-runtime-dirty",
                title="Runtime files changed; frozen acceptance gates required",
                category="gate_coverage",
                severity="medium",
                summary="Runtime edits detected; ensure frozen AT gates are run before promotion.",
                evidence=touched_runtime[:10],
                files=touched_runtime[:20],
                suggestion=f"Run scripts/acceptance/run_acceptance.py --ids {','.join(RUNTIME_GATES)}",
            )
        )
    return findings
