from __future__ import annotations

import json
from pathlib import Path

from src.runtime.telegram_router import TelegramRouter


GOLDEN = json.loads((Path(__file__).parent / "golden" / "status_shape.json").read_text(encoding="utf-8"))


def test_status_top_level_shape(monkeypatch) -> None:
    router = TelegramRouter()
    monkeypatch.setattr(
        router,
        "_task_loop_status",
        lambda: {
            "status": "ok",
            "last_event": {"status": "completed", "ts": "2026-02-07T00:00:00+00:00"},
        },
    )
    monkeypatch.setattr(router, "_supabase_health", lambda: {"status": "ok", "code": 200})
    monkeypatch.setattr(router, "_n8n_health", lambda: {"status": "ok", "code": 200})

    result = router.handle("/status")
    for key in GOLDEN["required_top_level_keys"]:
        assert key in result
    assert result["overall"]["status"] == "ok"
