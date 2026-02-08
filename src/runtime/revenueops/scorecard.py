from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple


@dataclass
class RevenueOpsMetrics:
    routing_success_rate: float
    evidence_delivery_success_rate: float
    dnc_compliance_rate: float
    outcome_completeness_rate: float


def _parse_simple_yaml(path: Path) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        out[key.strip()] = float(val.strip())
    return out


def load_thresholds(path: Path) -> Dict[str, float]:
    return _parse_simple_yaml(path)


def load_scorecard(path: Path) -> Dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "metrics" in payload and isinstance(payload["metrics"], dict):
        payload = payload["metrics"]

    def ratio(hit: str, total: str, explicit: str) -> float:
        if explicit in payload and payload[explicit] is not None:
            return float(payload[explicit])
        h = float(payload.get(hit, 0.0) or 0.0)
        t = float(payload.get(total, 0.0) or 0.0)
        return 0.0 if t <= 0 else h / t

    return {
        "routing_success_rate": ratio("routing_success", "routing_total", "routing_success_rate"),
        "evidence_delivery_success_rate": ratio("evidence_delivered", "evidence_total", "evidence_delivery_success_rate"),
        "dnc_compliance_rate": ratio("dnc_compliant", "dnc_total", "dnc_compliance_rate"),
        "outcome_completeness_rate": ratio("outcomes_complete", "outcomes_total", "outcome_completeness_rate"),
    }


def validate(metrics: Dict[str, float], thresholds: Dict[str, float]) -> Tuple[bool, Dict[str, Dict[str, float | bool]]]:
    detail: Dict[str, Dict[str, float | bool]] = {}
    ok = True
    for metric_key, threshold_key in [
        ("routing_success_rate", "routing_success_rate_min"),
        ("evidence_delivery_success_rate", "evidence_delivery_success_rate_min"),
        ("dnc_compliance_rate", "dnc_compliance_rate_min"),
        ("outcome_completeness_rate", "outcome_completeness_rate_min"),
    ]:
        value = float(metrics.get(metric_key, 0.0))
        minimum = float(thresholds.get(threshold_key, 0.0))
        passed = value >= minimum
        ok = ok and passed
        detail[metric_key] = {
            "value": round(value, 6),
            "minimum": round(minimum, 6),
            "pass": passed,
            "delta": round(value - minimum, 6),
        }
    return ok, detail
