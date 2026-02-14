from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .scorecard import load_scorecard
from .scorecard import load_thresholds
from .scorecard import validate


DEFAULT_THRESHOLDS = Path("config/revenueops_thresholds.yaml")
DEFAULT_SCORECARD = Path("tests/fixtures/revenueops/revenueops_scorecard_sample.json")


def run_gate(
    thresholds_path: Path = DEFAULT_THRESHOLDS,
    scorecard_path: Path = DEFAULT_SCORECARD,
) -> Dict[str, Any]:
    thresholds = load_thresholds(thresholds_path)
    metrics = load_scorecard(scorecard_path)
    ok, detail = validate(metrics, thresholds)
    failed = [k for k, v in detail.items() if not bool(v.get("pass"))]
    return {
        "gate": "AT-REV-001",
        "ok": ok,
        "metrics": metrics,
        "thresholds": thresholds,
        "detail": detail,
        "failed_metrics": failed,
    }
