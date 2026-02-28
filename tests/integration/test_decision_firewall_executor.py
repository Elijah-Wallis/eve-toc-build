from __future__ import annotations

import pytest

from src.runtime.action_executor import ActionExecutor
from src.runtime.decision_firewall import DecisionFirewall


def test_high_stakes_action_requires_clinician_gate() -> None:
    firewall = DecisionFirewall()
    result = firewall.evaluate("dosing_change", {"risk_tier": 3})
    assert result.allowed is False
    assert result.requires_clinician_review is True
    assert result.failure_code == "clinician_gate_required"


def test_action_executor_requires_valid_capability_token() -> None:
    firewall = DecisionFirewall()
    executor = ActionExecutor(firewall.tokens)

    with pytest.raises(RuntimeError):
        executor.execute(action="send_notification", token="invalid", payload={}, handler=lambda payload: {"ok": True})

    decision = firewall.evaluate("send_notification", {"risk_tier": 1})
    token = firewall.issue_capability_token(decision=decision, action_scope="send_notification", ttl_seconds=30)
    out = executor.execute(action="send_notification", token=token, payload={"x": 1}, handler=lambda payload: {"ok": payload["x"]})
    assert out == {"ok": 1}
