#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
PR_TEMPLATE = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
ONTOLOGY = ROOT / "ontology" / "schema.yml"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
PRECOMMIT = ROOT / ".pre-commit-config.yaml"


def must_contain(path: Path, required: list[str]) -> list[str]:
    if not path.exists():
        return [f"missing file: {path.relative_to(ROOT)}"]
    text = path.read_text(encoding="utf-8")
    missing = [needle for needle in required if needle not in text]
    return [f"{path.relative_to(ROOT)} missing text: {needle}" for needle in missing]


def _direct_data_access_hits(fp: Path) -> list[str]:
    text = fp.read_text(encoding="utf-8", errors="ignore")
    hits: list[str] = []

    if "from supabase" in text or "supabase." in text:
        hits.append("supabase-client-import")

    for line in text.splitlines():
        stripped = line.strip()
        if "requests." in stripped and ("supabase_url" in stripped or "/rest/v1" in stripped):
            hits.append("direct-supabase-requests-call")
            break

    return hits


def main() -> int:
    errors: list[str] = []

    errors += must_contain(
        README,
        [
            "Single Source of Truth (SSOT) Constitution",
            "Iron Law of the Ontology (Prime Directive)",
            "Highest Leverage Problem We Solve First and Forever",
            "Core Invariants",
            "1. All data access and transformations MUST route through the Ontology layer.",
            "2. The Ontology schema (defined in /ontology/) is the single canonical model.",
            "3. Every integration preserves provenance, auditability, and HIPAA-compliant lineage.",
            "4. Changes to the Ontology require explicit approval + update to this README section.",
            "5. Autonomy (AI decisions, scheduling, inventory, compliance) is built on top of the SSOT",
            "Any PR that introduces direct Supabase, raw SQL, or non-ontology data paths **will be rejected** by automated CI.",
        ],
    )

    errors += must_contain(
        PR_TEMPLATE,
        [
            "How does this PR strengthen the SSOT for data fragmentation?",
            "Does this PR protect the Ontology SSOT? (Y/N + link)",
            "This PR protects and strengthens the SSOT per the Iron Law (Prime Directive).",
        ],
    )

    errors += must_contain(
        CONTRIBUTING,
        [
            "Invariant #1",
            "No direct Supabase/REST/DB calls are allowed in production logic.",
        ],
    )

    errors += must_contain(
        ONTOLOGY,
        [
            "name: PatientJourney",
            "name: ClinicalEncounter",
            "name: AestheticProcedure",
            "name: Provider",
            "name: ClinicLocation",
            "name: ConsumableInventory",
            "name: FinancialEvent",
            "name: ComplianceRecord",
            "invariants:",
        ],
    )

    errors += must_contain(
        CODEOWNERS,
        [
            "/ontology/ @Elijah-Wallis",
            "README.md @Elijah-Wallis",
        ],
    )

    errors += must_contain(
        PRECOMMIT,
        [
            "id: ssot-lint",
            "python3 scripts/ci/lint_ssot_invariants.py",
        ],
    )

    scan_files = [
        *list((ROOT / "src" / "runtime").rglob("*.py")),
        *list((ROOT / "mcp_servers").rglob("*.py")),
        ROOT / "scripts" / "import_medspa_csv.py",
        ROOT / "scripts" / "ops" / "sync_call_transcripts.py",
        ROOT / "scripts" / "deploy_retell_personalization_workflows.py",
    ]

    for fp in scan_files:
        if not fp.exists():
            continue
        rel = fp.relative_to(ROOT).as_posix()
        if rel == "ontology/client.py":
            continue
        hits = _direct_data_access_hits(fp)
        if hits:
            errors.append(f"direct data access outside ontology/client.py in {rel}: {', '.join(hits)}")

    if errors:
        for err in errors:
            print(f"[SSOT-LINT] {err}")
        return 1

    print("[SSOT-LINT] ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
