from __future__ import annotations

from src.runtime.transcript_capture import (
    extract_summary,
    extract_transcript_text,
    extract_turns,
    normalize_call_payload,
    normalize_outcome,
    summarize_answerer,
)


def test_turn_extraction_and_answerer_detection() -> None:
    payload = {
        "transcript_object": [
            {"role": "agent", "content": "Hi, this is Eve."},
            {"speaker": "user", "text": "You reached the front desk."},
        ]
    }
    turns = extract_turns(payload)
    assert len(turns) == 2
    text = extract_transcript_text(payload, turns)
    assert "front desk" in text.lower()
    assert summarize_answerer("", text) == "reception/front-desk"


def test_outcome_heuristics_when_explicit_value_missing() -> None:
    summary = "Reached voicemail and left message"
    transcript = "call forwarded to automatic voice message system"
    outcome = normalize_outcome({}, summary, transcript)
    assert outcome == "VOICEMAIL"


def test_normalize_call_payload_maps_core_fields() -> None:
    payload = {
        "call_status": "ended",
        "duration_ms": 12345,
        "recording_url": "https://cdn.retell.ai/recordings/c1.mp3",
        "call_analysis": {"call_summary": "Reception took the message"},
        "transcript_object": [{"role": "user", "content": "front desk here"}],
    }
    call_session = {"id": "s1", "lead_id": "l1", "retell_call_id": "c1", "agent_type": "B2B"}
    lead = {"source": "tx-medspa-2026-02-07", "business_name": "Example Spa", "phone": "+15551234567"}
    record, turns = normalize_call_payload(payload, call_session=call_session, lead=lead)
    assert record["retell_call_id"] == "c1"
    assert record["campaign_tag"] == "tx-medspa-2026-02-07"
    assert record["retell_call_status"] == "ended"
    assert record["duration_ms"] == 12345
    assert record["recording_url"] == "https://cdn.retell.ai/recordings/c1.mp3"
    assert extract_summary(payload) == "Reception took the message"
    assert len(turns) == 1
