from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List


def _hash_payload(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_validation_report_record(
    *,
    event_id: str,
    report_schema_version: str,
    failure_code: str,
    missing_predicates: List[str],
    provenance_pointers: List[str],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    normalized_failure = str(failure_code or "").strip()
    if not normalized_failure or normalized_failure == "validation_failed":
        raise ValueError("failure_code must be specific and machine-actionable")
    if not isinstance(missing_predicates, list) or not isinstance(provenance_pointers, list):
        raise ValueError("missing_predicates and provenance_pointers must be lists")
    now = datetime.now(timezone.utc).isoformat()
    return {
        "event_id": event_id,
        "report_schema_version": report_schema_version,
        "failure_code": normalized_failure,
        "missing_predicates": missing_predicates,
        "provenance_pointers": provenance_pointers,
        "report_payload": payload,
        "report_hash": _hash_payload(payload),
        "created_at": now,
    }


def build_quarantine_record(
    *,
    event_id: str,
    report_schema_version: str,
    failure_code: str,
    missing_predicates: List[str],
    provenance_pointers: List[str],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    report = build_validation_report_record(
        event_id=event_id,
        report_schema_version=report_schema_version,
        failure_code=failure_code,
        missing_predicates=missing_predicates,
        provenance_pointers=provenance_pointers,
        payload=payload,
    )
    return {
        "event_id": report["event_id"],
        "report_schema_version": report["report_schema_version"],
        "failure_code": report["failure_code"],
        "missing_predicates": report["missing_predicates"],
        "provenance_pointers": report["provenance_pointers"],
        "quarantine_payload": payload,
        "report_hash": report["report_hash"],
        "created_at": report["created_at"],
    }
