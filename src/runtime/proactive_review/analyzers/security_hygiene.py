from __future__ import annotations

from typing import List

from ..schemas import Finding


def analyze(ctx) -> List[Finding]:
    findings: List[Finding] = []
    cmd = "rg -n --hidden --no-ignore-vcs '(Bearer [A-Za-z0-9._\\-+/=]{12,}|SUPABASE_SERVICE_ROLE_KEY\\s*=)' . --glob '!.git/**'"
    scan = ctx.run_cmd(cmd, timeout=60)
    if scan["status"] == "blocked":
        ctx.add_skipped("security_hygiene", "command_blocked")
        return findings
    lines = [line for line in scan["stdout"].splitlines() if line.strip()]
    if lines:
        findings.append(
            Finding(
                finding_id="security-hygiene-secret-like-pattern",
                title="Secret-like pattern detected in repository scan",
                category="security_hygiene",
                severity="high",
                summary="Potential token or service-key pattern found in tracked content.",
                evidence=lines[:5],
                suggestion="Run secret exposure scan and remove any raw credentials from tracked files.",
            )
        )
    return findings
