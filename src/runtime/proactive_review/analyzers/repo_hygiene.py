from __future__ import annotations

from pathlib import Path
from typing import List

from ..schemas import Finding


def analyze(ctx) -> List[Finding]:
    findings: List[Finding] = []
    generated_dir = ctx.repo_root / "generated"
    if generated_dir.exists():
        size_proc = ctx.run_cmd("du -sm generated", timeout=30)
        size_mb = 0
        if size_proc["status"] == "pass" and size_proc["stdout"].strip():
            try:
                size_mb = int(size_proc["stdout"].split()[0])
            except Exception:
                size_mb = 0
        if size_mb > 100:
            findings.append(
                Finding(
                    finding_id="repo-hygiene-generated-bloat",
                    title="Large repo-local generated directory detected",
                    category="repo_hygiene",
                    severity="high",
                    summary=f"generated/ is {size_mb}MB; should live in state dir",
                    evidence=[f"generated_size_mb={size_mb}"],
                    files=["generated"],
                    suggestion="Move artifacts to ${OPENCLAW_STATE_DIR}/generated and keep generated/ ignored.",
                )
            )
    dockerignore = ctx.repo_root / ".dockerignore"
    if not dockerignore.exists():
        findings.append(
            Finding(
                finding_id="repo-hygiene-missing-dockerignore",
                title="Missing root .dockerignore",
                category="repo_hygiene",
                severity="medium",
                summary="Docker context exclusions may drift without root .dockerignore.",
                files=[".dockerignore"],
                suggestion="Add root .dockerignore with generated/, .git/, caches, node_modules.",
            )
        )
    return findings
