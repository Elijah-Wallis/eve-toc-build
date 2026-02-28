from __future__ import annotations

import os

import pytest

from src.runtime import orchestrator_runtime as orchestrator_module
from src.runtime.runtime_guard import RuntimeGuard


def test_runtime_guard_handles_transient_failures() -> None:
    guard = RuntimeGuard()
    calls = {"count": 0}

    def flaky() -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient")
        return "ok"

    result = guard.run_step("flaky_step", flaky, default="fallback")
    assert result == "ok"
    assert calls["count"] == 2


def test_orchestrator_role_split_routes_steps(monkeypatch) -> None:
    monkeypatch.setenv("OPENCLAW_RUNTIME_ROLE", "scheduler")
    runtime = orchestrator_module.OrchestratorRuntime()
    called = {"auto": 0, "cron": 0, "queue": 0, "run_once": 0}

    runtime._auto_enqueue_packs = lambda: called.__setitem__("auto", called["auto"] + 1)  # type: ignore[attr-defined]
    runtime.cron.tick = lambda: called.__setitem__("cron", called["cron"] + 1) or 1  # type: ignore[attr-defined]
    runtime._drain_command_queue = lambda: called.__setitem__("queue", called["queue"] + 1)  # type: ignore[attr-defined]
    runtime.engine.run_once = lambda limit=10: called.__setitem__("run_once", called["run_once"] + 1) or 1  # type: ignore[attr-defined]

    def one_loop(_seconds: int) -> None:
        raise SystemExit(0)

    monkeypatch.setattr(orchestrator_module.time, "sleep", one_loop)
    with pytest.raises(SystemExit):
        runtime.run_loop(interval_seconds=0)

    assert called["auto"] == 1
    assert called["cron"] == 1
    assert called["queue"] == 1
    assert called["run_once"] == 0


def test_command_queue_bridge_consumes_lines(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENCLAW_RUNTIME_ROLE", "all")
    queue_file = tmp_path / "command_queue.txt"
    queue_file.write_text("/status\n/tasks\n", encoding="utf-8")
    monkeypatch.setenv("OPENCLAW_COMMAND_QUEUE_FILE", str(queue_file))

    runtime = orchestrator_module.OrchestratorRuntime()
    runtime._command_queue = queue_file
    seen: list[str] = []
    runtime.telegram.handle = lambda cmd: seen.append(cmd) or {"status": "ok"}  # type: ignore[assignment]
    runtime._drain_command_queue()

    assert seen == ["/status", "/tasks"]
    assert queue_file.read_text(encoding="utf-8") == ""
