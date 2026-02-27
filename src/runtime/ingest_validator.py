from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .shacl_artifacts import build_quarantine_record
from .shacl_artifacts import build_validation_report_record


REPORT_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class IngestValidationFailure:
    event_id: str
    failure_code: str
    missing_predicates: List[str]
    provenance_pointers: List[str]
    payload: Dict[str, Any]


def _extract_summary(payload: Dict[str, Any]) -> str:
    analysis = payload.get("call_analysis") or payload.get("analysis") or {}
    for key in ("call_summary", "summary"):
        value = analysis.get(key) if isinstance(analysis, dict) else None
        if value and str(value).strip():
            return str(value).strip()
        direct = payload.get(key)
        if direct and str(direct).strip():
            return str(direct).strip()
    return ""


def _extract_transcript_presence(payload: Dict[str, Any]) -> bool:
    for key in ("transcript", "transcript_text", "call_transcript"):
        value = payload.get(key)
        if value and str(value).strip():
            return True
    for key in ("transcript_object", "transcript_items", "messages", "conversation"):
        value = payload.get(key)
        if isinstance(value, list) and len(value) > 0:
            return True
    return False


def validate_retell_payload(
    *,
    payload: Dict[str, Any],
    event_id: str,
    provenance_pointers: List[str],
) -> IngestValidationFailure | None:
    if not isinstance(payload, dict) or not payload:
        return IngestValidationFailure(
            event_id=event_id,
            failure_code="empty_payload",
            missing_predicates=["retell:payload"],
            provenance_pointers=provenance_pointers,
            payload={"payload": payload},
        )

    missing: List[str] = []
    if not _extract_summary(payload):
        missing.append("retell:call_summary")
    if not _extract_transcript_presence(payload):
        missing.append("retell:transcript")
    if not (payload.get("call_status") or payload.get("status")):
        missing.append("retell:call_status")

    if not missing:
        return None

    return IngestValidationFailure(
        event_id=event_id,
        failure_code="missing_required_predicates",
        missing_predicates=missing,
        provenance_pointers=provenance_pointers,
        payload=payload,
    )


def build_persistence_records(failure: IngestValidationFailure) -> tuple[Dict[str, Any], Dict[str, Any]]:
    report = build_validation_report_record(
        event_id=failure.event_id,
        report_schema_version=REPORT_SCHEMA_VERSION,
        failure_code=failure.failure_code,
        missing_predicates=failure.missing_predicates,
        provenance_pointers=failure.provenance_pointers,
        payload=failure.payload,
    )
    quarantine = build_quarantine_record(
        event_id=failure.event_id,
        report_schema_version=REPORT_SCHEMA_VERSION,
        failure_code=failure.failure_code,
        missing_predicates=failure.missing_predicates,
        provenance_pointers=failure.provenance_pointers,
        payload=failure.payload,
    )
    return report, quarantine
