from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.runtime.telegram_router import TelegramRouter


@pytest.fixture(autouse=True)
def _stub_required_env(monkeypatch, tmp_path: Path) -> None:
    # TelegramRouter initializes TaskEngine which requires Supabase config; make tests hermetic.
    monkeypatch.setenv("SUPABASE_URL", "http://example.invalid")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service_role_test_key")
    monkeypatch.setenv("N8N_PUBLIC_WEBHOOK_BASE", "http://example.invalid/webhook")
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path))


def test_evebot_run_runs_inline_and_reports_metadata(monkeypatch, tmp_path: Path) -> None:
    router = TelegramRouter()

    hb_path = tmp_path / "heartbeat" / "elijah_evebot_heartbeat.json"
    hb_path.parent.mkdir(parents=True, exist_ok=True)
    hb_path.write_text(
        json.dumps({"run_id": "run-old", "finished_at": "2026-02-09T00:00:00+00:00", "repo_commit": "old"}),
        encoding="utf-8",
    )

    def fake_run(args, timeout_s, cwd=None):
        hb_path.write_text(
            json.dumps(
                {
                    "run_id": "run-new",
                    "finished_at": "2026-02-09T01:00:00+00:00",
                    "repo_commit": "new",
                    "counts": {"findings": 1, "proposals_generated": 2},
                }
            ),
            encoding="utf-8",
        )
        return {"ok": True, "code": 0, "stdout": "", "stderr": "", "error": None}

    monkeypatch.setattr(router, "_run_allowed_command", fake_run)
    out = router.handle("/evebot_run")
    assert "run_id: run-new" in out
    assert "finished_at: 2026-02-09T01:00:00+00:00" in out
    assert "repo_commit: new" in out
    assert "counts: findings=1, proposals_generated=2" in out


def test_evebot_digest_missing_report(monkeypatch, tmp_path: Path) -> None:
    router = TelegramRouter()
    out = router.handle("/evebot_digest")
    assert "No latest report found" in out


def test_evebot_digest_formats_top3(monkeypatch, tmp_path: Path) -> None:
    report = tmp_path / "reports" / "daily" / "LATEST_REPORT.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    hb = tmp_path / "heartbeat" / "elijah_evebot_heartbeat.json"
    hb.parent.mkdir(parents=True, exist_ok=True)
    hb.write_text(
        json.dumps(
            {
                "run_id": "run-123",
                "finished_at": "2026-02-09T16:13:01.120367+00:00",
                "repo_commit": "abc123",
                "dirty_worktree": True,
            }
        ),
        encoding="utf-8",
    )
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
    assert "run_id: run-123" in out
    assert "repo_commit: abc123" in out
    assert "dirty_worktree: true" in out
    assert "Top proposals (showing up to 3): 3 available" in out
    assert "p1" in out and "p2" in out and "p3" in out
    assert "Blockers" in out
    assert "Apply order" in out


def test_evebot_digest_includes_shortfall_reason(monkeypatch, tmp_path: Path) -> None:
    report = tmp_path / "reports" / "daily" / "LATEST_REPORT.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    hb = tmp_path / "heartbeat" / "elijah_evebot_heartbeat.json"
    hb.parent.mkdir(parents=True, exist_ok=True)
    hb.write_text(
        json.dumps(
            {
                "run_id": "run-456",
                "finished_at": "2026-02-09T16:13:01.120367+00:00",
                "repo_commit": "def456",
                "dirty_worktree": False,
            }
        ),
        encoding="utf-8",
    )
    payload = {
        "top_proposals": [
            {
                "proposal_id": "p1",
                "title": "Run gates",
                "why": "validate runtime edits",
                "depends_on": [],
                "proposal_kind": "validate_only",
                "execution_commands": ["python3 scripts/acceptance/run_acceptance.py --ids AT-001"],
            },
        ],
        "target_top_proposals": 10,
        "actual_top_proposals": 1,
        "proposal_shortfall_reason": "only_1_finding_generated",
        "blocked_actions": [],
        "skipped_checks": [],
    }
    report.write_text(json.dumps(payload), encoding="utf-8")

    router = TelegramRouter()
    out = router.handle("/evebot_digest")
    assert "run_id: run-456" in out
    assert "dirty_worktree: false" in out
    assert "top_proposals: 1/10" in out
    assert "Top proposals (showing up to 3): 1 available" in out
    assert "Shortfall reason: only_1_finding_generated" in out
    assert "proposal_kind: validate_only" in out
    assert "commands:" in out
    assert "python3 scripts/acceptance/run_acceptance.py --ids AT-001" in out
