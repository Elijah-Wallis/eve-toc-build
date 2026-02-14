from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List

from ..schemas import Finding

if TYPE_CHECKING:
    from ..daily_review import ReviewContext


def analyze(ctx: ReviewContext) -> List[Finding]:
    findings: List[Finding] = []
    schema = Path(ctx.repo_root / "supabase" / "schema.sql")
    upgrades = sorted(Path(ctx.repo_root / "supabase").glob("upgrade*.sql"))

    if not schema.exists():
        findings.append(
            Finding(
                finding_id="schema-drift-missing-schema",
                title="schema drift risk: supabase/schema.sql missing",
                category="schema_drift",
                severity="high",
                summary="Canonical schema file missing; migration drift cannot be validated.",
                evidence=["supabase/schema.sql missing"],
                files=["supabase/schema.sql"],
                suggestion="Restore schema.sql and align migrations before deployment.",
            )
        )

    if schema.exists() and not upgrades:
        findings.append(
            Finding(
                finding_id="schema-drift-no-upgrades",
                title="schema drift risk: no upgrade scripts found",
                category="schema_drift",
                severity="low",
                summary="No upgrade scripts were found; verify migration strategy is intentional.",
                evidence=["No supabase/upgrade*.sql files"],
                files=["supabase"],
                suggestion="Add explicit migration files or document why schema is static.",
            )
        )

    ctx.report_sections["schema_drift"] = {
        "schema_exists": schema.exists(),
        "upgrade_count": len(upgrades),
    }
    return findings
