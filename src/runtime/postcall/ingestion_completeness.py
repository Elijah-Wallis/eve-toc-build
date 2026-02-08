from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_EVIDENCE_FIELDS = ("evidence_type", "test_result", "test_timestamp")


@dataclass
class ValidationFailure:
    sample: str
    missing: List[str]


def validate_payload(payload: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    if not str(payload.get("outcome") or "").strip():
        missing.append("outcome")
    if not str(payload.get("summary") or "").strip():
        missing.append("summary")
    for field in REQUIRED_EVIDENCE_FIELDS:
        if not str(payload.get(field) or "").strip():
            missing.append(field)
    return missing


def validate_fixture_dir(samples_dir: Path) -> Dict[str, Any]:
    failures: List[ValidationFailure] = []
    for sample in sorted(samples_dir.glob("*.json")):
        payload = json.loads(sample.read_text(encoding="utf-8"))
        missing = validate_payload(payload)
        if missing:
            failures.append(ValidationFailure(sample=sample.name, missing=missing))
    return {
        "gate": "AT-ING-001",
        "ok": len(failures) == 0,
        "failures": [{"sample": f.sample, "missing": f.missing} for f in failures],
    }


def run_gate(samples_dir: Path = Path("tests/fixtures/postcall")) -> Dict[str, Any]:
    return validate_fixture_dir(samples_dir)
