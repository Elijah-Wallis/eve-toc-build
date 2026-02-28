from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


VALID_OUTCOMES = {"GRANTED", "STALLED", "REVOKED", "VOICEMAIL", "GATEKEEPER"}


def normalize_outcome(payload: Dict[str, Any], summary: str, transcript_text: str) -> Optional[str]:
    analysis = payload.get("call_analysis") or payload.get("analysis") or {}
    custom = analysis.get("custom_analysis_data") or {}
    candidates = [
        custom.get("call_outcome"),
        analysis.get("call_outcome"),
        analysis.get("disposition"),
        payload.get("call_outcome"),
        payload.get("disposition"),
        payload.get("outcome"),
    ]
    for raw in candidates:
        if not raw:
            continue
        value = str(raw).strip().upper()
        if value in VALID_OUTCOMES:
            return value

    signal = f"{summary}\n{transcript_text}".lower()
    if not signal.strip():
        return None
    if "voicemail" in signal or "voice message system" in signal:
        return "VOICEMAIL"
    if "front desk" in signal or "reception" in signal or "gatekeeper" in signal:
        return "GATEKEEPER"
    if "do not call" in signal or "not interested" in signal or "stop contact" in signal:
        return "REVOKED"
    if "booked" in signal or "appointment set" in signal or "send the report" in signal:
        return "GRANTED"
    return "STALLED"


def extract_summary(payload: Dict[str, Any]) -> str:
    analysis = payload.get("call_analysis") or payload.get("analysis") or {}
    custom = analysis.get("custom_analysis_data") or {}
    for value in (
        analysis.get("call_summary"),
        payload.get("call_summary"),
        payload.get("summary"),
        custom.get("summary"),
    ):
        if value and str(value).strip():
            return str(value).strip()
    return ""


def extract_turns(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates = [
        payload.get("transcript_object"),
        payload.get("transcript_items"),
        payload.get("messages"),
        payload.get("conversation"),
    ]
    turns: List[Dict[str, Any]] = []
    for source in candidates:
        if not isinstance(source, list):
            continue
        for item in source:
            if not isinstance(item, dict):
                continue
            speaker = (
                item.get("role")
                or item.get("speaker")
                or item.get("name")
                or item.get("actor")
                or item.get("participant")
                or "unknown"
            )
            text = (
                item.get("content")
                or item.get("text")
                or item.get("utterance")
                or item.get("message")
                or ""
            )
            text = " ".join(str(text).split())
            if not text:
                continue
            turns.append(
                {
                    "speaker": str(speaker).strip().lower(),
                    "text": text,
                    "start_ms": _to_ms(item.get("start_ms") or item.get("start") or item.get("start_time")),
                    "end_ms": _to_ms(item.get("end_ms") or item.get("end") or item.get("end_time")),
                    "confidence": _to_float(item.get("confidence") or item.get("score")),
                    "payload_json": item,
                }
            )
        if turns:
            break
    for idx, row in enumerate(turns):
        row["turn_index"] = idx
    return turns


def extract_transcript_text(payload: Dict[str, Any], turns: List[Dict[str, Any]]) -> str:
    for value in (payload.get("transcript"), payload.get("transcript_text"), payload.get("call_transcript")):
        if value and str(value).strip():
            return str(value).strip()
    if turns:
        return "\n".join(f"{turn['speaker']}: {turn['text']}" for turn in turns)
    return ""


def normalize_call_payload(
    payload: Dict[str, Any],
    *,
    call_session: Dict[str, Any],
    lead: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    turns = extract_turns(payload)
    summary = extract_summary(payload)
    transcript_text = extract_transcript_text(payload, turns)
    outcome = normalize_outcome(payload, summary, transcript_text)
    analysis = payload.get("call_analysis") or payload.get("analysis") or {}
    custom = analysis.get("custom_analysis_data") or {}
    dm_email = custom.get("email") or analysis.get("email") or payload.get("email")
    duration_ms = _normalize_duration_ms(
        payload.get("duration_ms")
        or payload.get("call_duration")
        or payload.get("duration")
    )
    recording_url = extract_recording_url(payload)

    record = {
        "call_session_id": call_session.get("id"),
        "lead_id": call_session.get("lead_id"),
        "retell_call_id": call_session.get("retell_call_id"),
        "source": "retell",
        "campaign_tag": lead.get("source"),
        "business_name": lead.get("business_name"),
        "phone": lead.get("phone"),
        "agent_type": call_session.get("agent_type"),
        "retell_call_status": payload.get("call_status") or payload.get("status"),
        "outcome": outcome,
        "summary": summary or None,
        "transcript_text": transcript_text,
        "duration_ms": duration_ms,
        "recording_url": recording_url,
        "dm_email": dm_email,
        "start_timestamp": _to_timestamptz(
            payload.get("start_timestamp") or payload.get("start_time") or payload.get("start_ts")
        ),
        "end_timestamp": _to_timestamptz(
            payload.get("end_timestamp") or payload.get("end_time") or payload.get("end_ts")
        ),
        "payload_json": payload,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return record, turns


def extract_recording_url(payload: Dict[str, Any]) -> Optional[str]:
    analysis = payload.get("call_analysis") or payload.get("analysis") or {}
    custom = analysis.get("custom_analysis_data") or {}
    candidates = [
        payload.get("recording_url"),
        payload.get("recordingUrl"),
        payload.get("call_recording_url"),
        payload.get("recording"),
        payload.get("recording_uri"),
        analysis.get("recording_url"),
        analysis.get("recordingUrl"),
        analysis.get("call_recording_url"),
        custom.get("recording_url"),
        custom.get("recordingUrl"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            for key in ("url", "recording_url", "download_url", "uri"):
                value = candidate.get(key)
                if value and str(value).strip():
                    return str(value).strip()
            continue
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return None


def summarize_answerer(summary: str, transcript_text: str) -> str:
    haystack = f"{summary}\n{transcript_text}".lower()
    if "voicemail" in haystack or "voice message system" in haystack:
        return "voicemail"
    if "front desk" in haystack or "reception" in haystack or "gatekeeper" in haystack:
        return "reception/front-desk"
    if haystack.strip():
        return "human-answered-unspecified"
    return "unknown"


def _to_ms(value: Any) -> Optional[int]:
    number = _to_float(value)
    if number is None:
        return None
    if number < 0:
        return None
    if number < 10000:
        return int(round(number * 1000.0))
    return int(round(number))


def _normalize_duration_ms(value: Any) -> Optional[int]:
    number = _to_float(value)
    if number is None or number <= 0:
        return None
    if number < 10000:
        return int(round(number * 1000.0))
    return int(round(number))


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_timestamptz(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return _from_epoch(float(value))

    raw = str(value).strip()
    if not raw:
        return None
    maybe_number = _to_float(raw)
    if maybe_number is not None:
        return _from_epoch(maybe_number)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _from_epoch(number: float) -> Optional[str]:
    if number <= 0:
        return None
    if number > 10_000_000_000:
        number = number / 1000.0
    try:
        parsed = datetime.fromtimestamp(number, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    return parsed.isoformat()
