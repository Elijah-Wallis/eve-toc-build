from __future__ import annotations

from src.runtime.proactive_review.daily_review import load_execution_profiles


def test_execution_profiles_load_default_canary() -> None:
    profiles = load_execution_profiles()
    assert "canary" in profiles
    assert "prod" in profiles
    assert profiles["canary"]["max_top_proposals"] == 10
