from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .config_adapter import resolve_command_queue_file, resolve_telemetry_path
from .context_store import ContextStore
from .cron_scheduler import CronScheduler
from .env_loader import load_env_file
from .model_router import ModelRouter
from .registry_defaults import build_registry
from .runtime_paths import state_path
from .runtime_guard import RuntimeGuard
from .task_engine import TaskEngine
from .telemetry import Telemetry
from .telegram_router import TelegramRouter


class OrchestratorRuntime:
    """Runtime loop with step-level crash boundaries and role-based execution.

    Custom LLM (BYOM) routing: use the same Retell agent_id that was configured with
    scripts/configure_retell_b2b_agent.py --custom-llm; n8n dispatch uses that agent_id.
    """

    def __init__(self) -> None:
        load_env_file()
        self.role = str(os.environ.get("OPENCLAW_RUNTIME_ROLE", "all")).strip().lower()
        if self.role not in {"all", "scheduler", "worker"}:
            self.role = "all"

        self.registry = build_registry()
        self.telemetry = Telemetry(str(resolve_telemetry_path()))
        self.guard = RuntimeGuard(self.telemetry)
        self.engine = TaskEngine(self.registry, telemetry=self.telemetry)
        self.context = ContextStore()
        self.model_router = ModelRouter(str(state_path("omega", "ledger.jsonl")))
        self.telegram = TelegramRouter()
        self.cron = CronScheduler(self.engine, telemetry=self.telemetry)

        self._last_enqueued: Dict[str, datetime] = {}
        self._command_queue = self._load_command_queue_path()
        self._task_batch_size = max(1, int(os.environ.get("OPENCLAW_TASK_BATCH_SIZE", "10")))

    def run_loop(self, interval_seconds: int = 15) -> None:
        while True:
            loop_corr = self.telemetry.new_correlation_id("loop")
            self.telemetry.set_context(correlation_id=loop_corr, runtime_role=self.role)

            cron_fired = 0
            processed = 0
            if self.role in {"all", "scheduler"}:
                self.guard.run_step("auto_enqueue", self._auto_enqueue_packs)
                cron_fired = self.guard.run_step("cron_tick", self.cron.tick, default=0) or 0
                self.guard.run_step("command_queue_drain", self._drain_command_queue)

            if self.role in {"all", "worker"}:
                processed = (
                    self.guard.run_step(
                        "task_engine_run_once",
                        lambda: self.engine.run_once(limit=self._task_batch_size),
                        default=0,
                    )
                    or 0
                )

            self.telemetry.emit(
                "runtime_loop",
                {
                    "role": self.role,
                    "cron_fired": int(cron_fired),
                    "processed": int(processed),
                    "interval_seconds": interval_seconds,
                },
            )
            self.telemetry.clear_context("correlation_id")
            time.sleep(interval_seconds)

    def _auto_enqueue_packs(self) -> None:
        now = datetime.now(timezone.utc)
        self._maybe_enqueue(
            "pack_lead_ops",
            now,
            interval_minutes=60,
            tasks=[
                {
                    "type": "n8n.trigger",
                    "payload": {
                        "workflow": "openclaw-apify-ingest",
                        "data": {
                            "sync_reason": "prebatch_kb_sync",
                            "force_kb_sync": True,
                        },
                    },
                },
                {
                    "type": "n8n.trigger",
                    "payload": {
                        "workflow": "openclaw-retell-dispatch",
                        "data": {
                            "require_kb_sync": True,
                            "kb_sync_wait_seconds": 60,
                            "abort_on_missing_promo_fields": True,
                        },
                    },
                },
                {"type": "n8n.trigger", "payload": {"workflow": "openclaw-nurture-run", "data": {}}},
            ],
        )
        self._maybe_enqueue(
            "pack_sales_intel",
            now,
            interval_minutes=1440,
            tasks=[{"type": "reports.daily", "payload": {}}],
        )
        self._maybe_enqueue(
            "pack_postcall_reconcile",
            now,
            interval_minutes=5,
            tasks=[
                {
                    "type": "retell.postcall.reconcile",
                    "payload": {"lookback_hours": 96, "limit": 400, "unresolved_only": True},
                }
            ],
        )

    def _maybe_enqueue(self, key: str, now: datetime, interval_minutes: int, tasks: Any) -> None:
        last = self._last_enqueued.get(key)
        if last and now - last < timedelta(minutes=interval_minutes):
            return
        for task in tasks:
            self.engine.enqueue(task["type"], task["payload"])
        self._last_enqueued[key] = now
        self.telemetry.emit("runtime_auto_enqueue", {"pack": key, "task_count": len(tasks)})

    def trigger_graph_from_telegram(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        graph = payload.get("graph")
        if not graph:
            raise RuntimeError("graph is required")
        thread_name = payload.get("thread_name") or "telegram"
        thread = self.context.create_thread(thread_name)
        self.context.append_event(thread["id"], "telegram_graph_request", payload)
        return {"status": "queued", "thread_id": thread["id"]}

    def _load_command_queue_path(self) -> Optional[Path]:
        return resolve_command_queue_file()

    def _drain_command_queue(self) -> None:
        if not self._command_queue or not self._command_queue.exists():
            return
        try:
            content = self._command_queue.read_text(encoding="utf-8").strip()
        except OSError:
            return
        if not content:
            return
        commands = [line for line in content.splitlines() if line.strip()]
        try:
            self._command_queue.write_text("", encoding="utf-8")
        except OSError:
            return
        for cmd in commands:
            result = self.telegram.handle(cmd)
            self.telemetry.emit("command_queue", {"command": cmd, "result": result})


def main() -> int:
    interval = int(os.environ.get("OPENCLAW_TASK_LOOP_INTERVAL", "15"))
    runtime = OrchestratorRuntime()
    try:
        runtime.run_loop(interval_seconds=interval)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
