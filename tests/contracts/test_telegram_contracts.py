from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from src.runtime.telegram_router import TelegramRouter
from src.runtime.runtime_paths import resolve_repo_root


GOLDEN_DIR = Path(__file__).parent / "golden"


def _load_golden(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def test_launch_medspa_defaults_manual(monkeypatch) -> None:
    router = TelegramRouter()
    monkeypatch.setattr(router.engine, "enqueue", lambda task_type, payload: {"id": "task-1", "type": task_type, "payload": payload})
    result = router.handle("/launch-medspa tx-medspa-2026-02-07")

    golden = _load_golden("launch_medspa_default.json")
    for key in golden["required_keys"]:
        assert key in result
    assert result["status"] == golden["status"]
    assert result["mode"] == golden["mode"]
    assert result["profile"] == golden["profile"]
    assert result["campaign_tag"] == "tx-medspa-2026-02-07"


def test_runpack_contract(monkeypatch) -> None:
    router = TelegramRouter()
    monkeypatch.setattr(router, "_launch_path_gate", lambda workflow: None)
    monkeypatch.setattr(router, "_upsert_cron_job", lambda workflow, cron: {"id": "cron-1", "name": f"cron:{workflow}"})
    monkeypatch.setattr(router.engine, "enqueue", lambda task_type, payload: {"id": "task-2", "type": task_type, "payload": payload})

    result = router.handle("/runpack openclaw-retell-dispatch")
    golden = _load_golden("runpack_shape.json")
    for key in golden["required_keys"]:
        assert key in result
    assert result["status"] in golden["allowed_status"]
    assert result["task"]["type"] == "n8n.trigger"


def test_evebot_run_kickstart_command(monkeypatch) -> None:
    router = TelegramRouter()
    captured: dict = {}

    def fake_run(args, timeout_s, cwd=None):
        captured["args"] = args
        captured["timeout_s"] = timeout_s
        captured["cwd"] = cwd
        return {"ok": True, "code": 0, "stdout": "", "stderr": "", "error": None}

    monkeypatch.setattr(router, "_run_allowed_command", fake_run)
    result = router.handle("/evebot_run")
    assert result == "Started daily run. Check /evebot_status in ~30–60s."
    assert captured["args"] == ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{router.DAILY_LABEL}"]
    assert captured["timeout_s"] == 5


def test_evebot_deep_missing_plist(monkeypatch, tmp_path: Path) -> None:
    router = TelegramRouter()
    monkeypatch.setattr("src.runtime.telegram_router.Path.home", lambda: tmp_path)
    result = router.handle("/evebot_deep")
    assert result == "Weekly deep not installed. Run: install_elijah_evebot_launchd.sh --with-weekly-deep"


def test_evebot_deep_installed_but_kickstart_fails(monkeypatch, tmp_path: Path) -> None:
    router = TelegramRouter()
    launch_agents = tmp_path / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True, exist_ok=True)
    (launch_agents / f"{router.WEEKLY_LABEL}.plist").write_text("plist", encoding="utf-8")
    monkeypatch.setattr("src.runtime.telegram_router.Path.home", lambda: tmp_path)
    monkeypatch.setattr(
        router,
        "_run_allowed_command",
        lambda args, timeout_s, cwd=None: {"ok": False, "code": 1, "stdout": "", "stderr": "x", "error": None},
    )
    result = router.handle("/evebot_deep")
    assert (
        result
        == "Weekly deep is installed but not loaded. Run installer again to bootstrap it: "
        "install_elijah_evebot_launchd.sh --with-weekly-deep"
    )


def test_evebot_status_missing_heartbeat(monkeypatch, tmp_path: Path) -> None:
    router = TelegramRouter()
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path))
    result = router.handle("/evebot_status")
    assert result == "No heartbeat found yet. Send /evebot_run to start."


def test_evebot_status_formats_heartbeat(monkeypatch, tmp_path: Path) -> None:
    router = TelegramRouter()
    tmp_state_dir = tmp_path / "state"
    (tmp_state_dir / "heartbeat").mkdir(parents=True, exist_ok=True)
    hb_path = tmp_state_dir / "heartbeat" / "elijah_evebot_heartbeat.json"
    hb_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "repo_commit": "abc123",
                "finished_at": "2026-02-08T08:10:00Z",
                "counts": {"findings": 3, "proposals_generated": 5, "patches_emitted": 2},
                "pointers": {
                    "latest_report_markdown": "/tmp/latest.md",
                    "latest_report_json": "/tmp/latest.json",
                    "latest_proposals": "/tmp/proposals/latest",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_state_dir))
    result = router.handle("/evebot_status")
    assert "status: ok" in result
    assert "repo_commit: abc123" in result
    assert "finished_at: 2026-02-08T08:10:00Z" in result
    assert "findings=3" in result
    assert "proposals_generated=5" in result
    assert "patches_emitted=2" in result


def test_evebot_heartbeat_now_runs_from_repo_root(monkeypatch) -> None:
    router = TelegramRouter()
    captured: dict = {}

    def fake_run(args, timeout_s, cwd=None):
        captured["args"] = args
        captured["timeout_s"] = timeout_s
        captured["cwd"] = cwd
        return {"ok": True, "code": 0, "stdout": "", "stderr": "", "error": None}

    monkeypatch.setattr(router, "_run_allowed_command", fake_run)
    result = router.handle("/evebot_heartbeat_now")
    assert result == "Heartbeat refreshed. Use /evebot_status."
    assert captured["args"][0] == sys.executable
    assert captured["cwd"] == resolve_repo_root()
    assert captured["timeout_s"] == 20


def test_evebot_blocks_disallowed_command() -> None:
    router = TelegramRouter()
    blocked_git = router._run_allowed_command(["git", "push"], timeout_s=5)
    blocked_curl = router._run_allowed_command(["curl", "x"], timeout_s=5)
    assert blocked_git["ok"] is False
    assert blocked_curl["ok"] is False
    assert "allowlisted" in (blocked_git.get("error") or "")
    assert "allowlisted" in (blocked_curl.get("error") or "")
