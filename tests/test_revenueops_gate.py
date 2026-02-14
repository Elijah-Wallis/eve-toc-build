from __future__ import annotations

import json
from pathlib import Path

from src.runtime.revenueops.gate_rev_001 import run_gate


def test_revenueops_gate_passes_fixture() -> None:
    result = run_gate()
    assert result["ok"] is True
    assert result["failed_metrics"] == []


def test_revenueops_gate_reports_precise_failures(tmp_path: Path) -> None:
    sample = {
        "metrics": {
            "routing_success_rate": 0.1,
            "evidence_delivery_success_rate": 0.2,
            "dnc_compliance_rate": 0.5,
            "outcome_completeness_rate": 0.6,
        }
    }
    p = tmp_path / "sample.json"
    p.write_text(json.dumps(sample), encoding="utf-8")
    result = run_gate(scorecard_path=p)
    assert result["ok"] is False
    assert set(result["failed_metrics"]) == {
        "routing_success_rate",
        "evidence_delivery_success_rate",
        "dnc_compliance_rate",
        "outcome_completeness_rate",
    }
    for metric in result["failed_metrics"]:
        assert result["detail"][metric]["pass"] is False
