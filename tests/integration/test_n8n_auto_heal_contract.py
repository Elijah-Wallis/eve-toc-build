from __future__ import annotations

from src.runtime import n8n_webhooks


def test_not_registered_404_triggers_single_auto_heal(monkeypatch) -> None:
    calls = {"post_candidates": 0, "recover": 0}

    def fake_post_candidates(candidates, data, timeout):  # noqa: ANN001
        calls["post_candidates"] += 1
        if calls["post_candidates"] == 1:
            return {
                "result": None,
                "attempts": [
                    {"url": "https://n8n/webhook/openclaw-retell-dispatch", "status_code": 404, "body": {"message": "not registered"}},
                    {"url": "https://n8n/webhook-test/openclaw-retell-dispatch", "status_code": 404, "body": {"message": "not registered"}},
                ],
            }
        return {
            "result": {"url": "https://n8n/webhook/openclaw-retell-dispatch", "status_code": 200, "body": {"status": "ok"}},
            "attempts": [{"url": "https://n8n/webhook/openclaw-retell-dispatch", "status_code": 200, "body": {"status": "ok"}}],
        }

    def fake_recover(**kwargs):  # noqa: ANN003
        calls["recover"] += 1
        return {"workflow_id": "wf-1", "activate_code": 200}

    monkeypatch.setattr(n8n_webhooks, "_post_candidates", fake_post_candidates)
    monkeypatch.setattr(n8n_webhooks, "_can_attempt_recovery", lambda workflow_path: True)
    monkeypatch.setattr(n8n_webhooks, "_recover_webhook_registration", fake_recover)

    out = n8n_webhooks.post_with_auto_heal(
        webhook_base="https://n8n.local",
        workflow_path="openclaw-retell-dispatch",
        data={},
        timeout=30,
        n8n_api_base="https://n8n.local/api/v1",
        n8n_api_key="k",
    )

    assert out["status_code"] == 200
    assert calls["recover"] == 1
    assert calls["post_candidates"] == 2
    assert "auto_heal" in out
