from __future__ import annotations

import json
from pathlib import Path

from src.runtime.telegram_router import TelegramRouter


def test_evebot_digest_missing_report(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path))
    router = TelegramRouter()
    out = router.handle("/evebot_digest")
    assert "No latest report found" in out


def test_evebot_digest_formats_top3(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path))
    report = tmp_path / "reports" / "daily" / "LATEST_REPORT.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "top_proposals": [
            {"proposal_id": "p1", "title": "Improve routing", "why": "lift bookings", "depends_on": []},
            {"proposal_id": "p2", "title": "Fix ingest", "why": "remove null outcomes", "depends_on": ["p1"]},
            {"proposal_id": "p3", "title": "Harden secrets", "why": "reduce leak risk", "depends_on": []},
        ],
        "blocked_actions": ["blocked: test"],
        "skipped_checks": [{"check": "x", "reason": "y"}],
    }
    report.write_text(json.dumps(payload), encoding="utf-8")

    router = TelegramRouter()
    out = router.handle("/evebot_digest")
    assert "Top 3 proposals" in out
    assert "p1" in out and "p2" in out and "p3" in out
    assert "Blockers" in out
    assert "Apply order" in out
