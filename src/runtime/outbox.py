from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _json_dumps(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def build_event_id(*, mutation_key: str, payload_delta: Dict[str, Any], schema_version: int = 1) -> str:
    canonical = {
        "mutation_key": str(mutation_key),
        "schema_version": int(schema_version),
        "payload_delta": payload_delta,
    }
    digest = hashlib.sha256(_json_dumps(canonical).encode("utf-8")).hexdigest()
    return f"evt_{digest[:24]}"


@dataclass(frozen=True)
class OutboxEnvelope:
    event_id: str
    mutation_key: str
    aggregate_type: str
    aggregate_id: str
    schema_version: int
    entity_key: str
    payload_delta: Dict[str, Any]
    created_at: str
    published_at: Optional[str] = None

    def as_record(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "mutation_key": self.mutation_key,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "schema_version": self.schema_version,
            "entity_key": self.entity_key,
            "payload_delta": self.payload_delta,
            "created_at": self.created_at,
            "published_at": self.published_at,
        }


def build_outbox_envelope(
    *,
    mutation_key: str,
    aggregate_type: str,
    aggregate_id: str,
    payload_delta: Dict[str, Any],
    schema_version: int = 1,
    event_id: Optional[str] = None,
) -> OutboxEnvelope:
    now = datetime.now(timezone.utc).isoformat()
    resolved_event_id = event_id or build_event_id(
        mutation_key=mutation_key,
        payload_delta=payload_delta,
        schema_version=schema_version,
    )
    return OutboxEnvelope(
        event_id=resolved_event_id,
        mutation_key=mutation_key,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        schema_version=schema_version,
        entity_key=f"{aggregate_type}:{aggregate_id}",
        payload_delta=payload_delta,
        created_at=now,
    )


def effectively_once_semantics_note() -> str:
    return (
        "Outbox delivery is effectively-once for side effects per event_id idempotency key; "
        "producers may retry transport, and consumers must dedupe by event_id."
    )
