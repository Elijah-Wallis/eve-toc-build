from __future__ import annotations

from src.runtime import telegram_router as router_module


def test_launch_gate_blocks_on_preflight_failure(monkeypatch) -> None:
    router = router_module.TelegramRouter()
    monkeypatch.setattr(
        router_module.MedspaLaunch,
        "preflight",
        lambda self: {
            "overall": "error",
            "overall_spatial": {"color": "RED"},
            "blockers": ["guardrail_workflows"],
        },
    )
    result = router._launch_path_gate("openclaw-retell-dispatch")
    assert result is not None
    assert result["status"] == "blocked"
    assert result["reason"] == "preflight_failed"


def test_launch_medspa_approve_contract(monkeypatch) -> None:
    router = router_module.TelegramRouter()
    monkeypatch.setattr(router.engine, "enqueue", lambda task_type, payload: {"id": "task-approve", "type": task_type, "payload": payload})
    result = router.handle("/launch-medspa-approve tx-medspa-2026-02-07")
    assert result["status"] == "queued"
    assert result["campaign_tag"] == "tx-medspa-2026-02-07"
    assert result["profile"] == "balanced"
    assert result["task"]["type"] == "medspa.ramp"
