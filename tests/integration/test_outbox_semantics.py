from __future__ import annotations

from src.runtime.outbox import build_event_id
from src.runtime.outbox import build_outbox_envelope
from src.runtime.outbox import effectively_once_semantics_note


def test_effectively_once_wording_and_event_id_contract() -> None:
    note = effectively_once_semantics_note().lower()
    assert "effectively-once" in note
    assert "event_id" in note

    payload = {"status": "queued", "task_id": "t-1"}
    event_id_a = build_event_id(mutation_key="tasks:t-1:update", payload_delta=payload, schema_version=1)
    event_id_b = build_event_id(mutation_key="tasks:t-1:update", payload_delta=payload, schema_version=1)
    assert event_id_a == event_id_b

    envelope = build_outbox_envelope(
        mutation_key="tasks:t-1:update",
        aggregate_type="task",
        aggregate_id="t-1",
        payload_delta=payload,
        schema_version=1,
    )
    record = envelope.as_record()
    assert record["event_id"].startswith("evt_")
    assert record["entity_key"] == "task:t-1"
    assert record["schema_version"] == 1
