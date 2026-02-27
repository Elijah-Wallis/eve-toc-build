from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.runtime.retell_protocol import RetellProtocolState
from src.runtime.retell_protocol import handle_event
from src.runtime.retell_protocol import heartbeat_stale


def test_keepalive_contract_has_ping_pong_requirements() -> None:
    state = RetellProtocolState(auto_reconnect=True)
    decision = handle_event(state, interaction_type="ping_pong")
    assert decision.send_ping_pong is True
    assert state.last_ping_pong_at is not None

    now = datetime.now(timezone.utc)
    state.last_ping_pong_at = now - timedelta(seconds=6)
    assert heartbeat_stale(state, now=now) is True

    state.last_ping_pong_at = now - timedelta(seconds=4)
    assert heartbeat_stale(state, now=now) is False


def test_preemption_contract_update_only_and_new_response_id() -> None:
    state = RetellProtocolState(auto_reconnect=True, generation_active=True, current_response_id="resp-a")

    # update_only must stop outbound stream but not cancel/discard.
    d1 = handle_event(state, interaction_type="update_only")
    assert d1.stop_outbound_streaming is True
    assert d1.cancel_generation is False
    assert d1.discard_buffer is False
    assert state.generation_active is True

    # New response_id on response_required must cancel old generation and discard buffer.
    d2 = handle_event(state, interaction_type="response_required", response_id="resp-b")
    assert d2.cancel_generation is True
    assert d2.discard_buffer is True
    assert d2.begin_generation is True
    assert state.current_response_id == "resp-b"
    assert state.generation_active is True
