from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List

from ..schemas import Finding

if TYPE_CHECKING:
    from ..daily_review import ReviewContext


def analyze(ctx: ReviewContext) -> List[Finding]:
    findings: List[Finding] = []
    schema = Path(ctx.repo_root / "ontology" / "schema.yml")
    upgrades = sorted(Path(ctx.repo_root / "supabase").glob("upgrade*.sql"))
    duplicate_schema_files = [
        str(path.relative_to(ctx.repo_root))
        for path in (
            Path(ctx.repo_root / "ontology" / "schema.sql"),
            Path(ctx.repo_root / "ontology" / "schema.json"),
        )
        if path.exists()
    ]

    if not schema.exists():
        findings.append(
            Finding(
                finding_id="schema-drift-missing-schema",
                title="schema drift risk: ontology/schema.yml missing",
                category="schema_drift",
                severity="high",
                summary="Canonical ontology schema missing; SSOT drift cannot be validated.",
                evidence=["ontology/schema.yml missing"],
                files=["ontology/schema.yml"],
                suggestion="Restore ontology/schema.yml before changing runtime or database schema.",
            )
        )

    if duplicate_schema_files:
        findings.append(
            Finding(
                finding_id="schema-drift-duplicate-ontology-schema",
                title="schema drift risk: duplicate ontology schema artifacts present",
                category="schema_drift",
                severity="high",
                summary="The ontology must have a single canonical schema definition under ontology/schema.yml.",
                evidence=duplicate_schema_files,
                files=duplicate_schema_files,
                suggestion="Remove duplicate ontology schema.sql/schema.json artifacts and derive any other schema forms from ontology/schema.yml.",
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
        "schema_path": str(schema.relative_to(ctx.repo_root)),
        "duplicate_schema_files": duplicate_schema_files,
        "upgrade_count": len(upgrades),
    }
    return findings
