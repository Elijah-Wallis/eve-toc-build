from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass
class RetellProtocolDecision:
    send_ping_pong: bool = False
    stop_outbound_streaming: bool = False
    cancel_generation: bool = False
    discard_buffer: bool = False
    begin_generation: bool = False


@dataclass
class RetellProtocolState:
    auto_reconnect: bool = False
    current_response_id: str = ""
    generation_active: bool = False
    outbound_streaming_enabled: bool = True
    last_ping_pong_at: Optional[datetime] = None


def handle_event(state: RetellProtocolState, *, interaction_type: str, response_id: str = "") -> RetellProtocolDecision:
    kind = str(interaction_type or "").strip().lower()
    rid = str(response_id or "").strip()
    decision = RetellProtocolDecision()

    if kind == "ping_pong":
        if state.auto_reconnect:
            decision.send_ping_pong = True
        state.last_ping_pong_at = datetime.now(timezone.utc)
        return decision

    if kind == "update_only":
        if state.generation_active:
            decision.stop_outbound_streaming = True
            state.outbound_streaming_enabled = False
        return decision

    if kind in {"response_required", "reminder_required"}:
        if state.generation_active and rid and rid != state.current_response_id:
            decision.cancel_generation = True
            decision.discard_buffer = True
        state.current_response_id = rid
        state.generation_active = True
        state.outbound_streaming_enabled = True
        decision.begin_generation = True
        return decision

    return decision


def heartbeat_stale(state: RetellProtocolState, *, now: Optional[datetime] = None) -> bool:
    if not state.auto_reconnect:
        return False
    if state.last_ping_pong_at is None:
        return True
    current = now or datetime.now(timezone.utc)
    return current - state.last_ping_pong_at > timedelta(seconds=5)
