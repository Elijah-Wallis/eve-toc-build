from __future__ import annotations

from pathlib import Path

from src.runtime.postcall.ingestion_completeness import run_gate
from src.runtime.postcall.ingestion_completeness import validate_payload


def test_validate_payload_flags_missing_required_fields() -> None:
    missing = validate_payload({"outcome": "", "summary": "", "evidence_type": "AUDIO"})
    assert "outcome" in missing
    assert "summary" in missing
    assert "test_result" in missing
    assert "test_timestamp" in missing


def test_gate_returns_failures_for_invalid_samples() -> None:
    result = run_gate(Path("tests/fixtures/postcall"))
    assert result["ok"] is False
    samples = {item["sample"] for item in result["failures"]}
    assert "missing_outcome.json" in samples
    assert "missing_summary.json" in samples
