from __future__ import annotations

import pytest
from pathlib import Path

from src.runtime.shacl_artifacts import build_quarantine_record
from src.runtime.shacl_artifacts import build_validation_report_record


def test_shacl_artifact_requires_structured_fields() -> None:
    payload = {"focusNode": "lead:123", "violations": [{"path": "ex:phone"}]}
    report = build_validation_report_record(
        event_id="evt_123",
        report_schema_version="1.0.0",
        failure_code="missing_required_predicate",
        missing_predicates=["ex:phone"],
        provenance_pointers=["ingest:lead_123"],
        payload=payload,
    )
    assert report["report_schema_version"] == "1.0.0"
    assert report["failure_code"] == "missing_required_predicate"
    assert report["missing_predicates"] == ["ex:phone"]
    assert report["provenance_pointers"] == ["ingest:lead_123"]
    assert report["report_hash"]

    quarantine = build_quarantine_record(
        event_id="evt_123",
        report_schema_version="1.0.0",
        failure_code="datatype_mismatch",
        missing_predicates=[],
        provenance_pointers=["provider:source_a"],
        payload=payload,
    )
    assert quarantine["failure_code"] == "datatype_mismatch"
    assert quarantine["provenance_pointers"] == ["provider:source_a"]


def test_shacl_artifact_rejects_generic_failure_code() -> None:
    with pytest.raises(ValueError):
        build_validation_report_record(
            event_id="evt_123",
            report_schema_version="1.0.0",
            failure_code="validation_failed",
            missing_predicates=[],
            provenance_pointers=[],
            payload={},
        )


def test_shacl_schema_includes_machine_actionable_fields() -> None:
    schema = Path(__file__).resolve().parents[2] / "supabase" / "schema.sql"
    text = schema.read_text(encoding="utf-8")
    for marker in [
        "report_schema_version",
        "failure_code",
        "missing_predicates",
        "provenance_pointers",
        "check (failure_code <> 'validation_failed')",
    ]:
        assert marker in text
