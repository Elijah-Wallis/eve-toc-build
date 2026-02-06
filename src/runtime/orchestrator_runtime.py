from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .context_store import ContextStore
from .env_loader import load_env_file
from .model_router import ModelRouter
from .registry_defaults import build_registry
from .task_engine import TaskEngine
from .telemetry import Telemetry
from .telegram_router import TelegramRouter
from .cron_scheduler import CronScheduler


class OrchestratorRuntime:
    """Runtime loop: auto-enqueue packs, scheduled task loop, Telegram graph trigger."""

    def __init__(self) -> None:
        load_env_file()
        self.registry = build_registry()
        self.telemetry = Telemetry(os.path.expanduser("~/.openclaw-eve/runtime/telemetry.jsonl"))
        self.engine = TaskEngine(self.registry, telemetry=self.telemetry)
        self.context = ContextStore()
        self.model_router = ModelRouter(os.path.expanduser("~/.openclaw-eve/omega/ledger.jsonl"))
        self.telegram = TelegramRouter()
        self.cron = CronScheduler(self.engine)

        self._last_enqueued: Dict[str, datetime] = {}
        self._command_queue = self._load_command_queue_path()

    def run_loop(self, interval_seconds: int = 15) -> None:
        while True:
            self._auto_enqueue_packs()
            self.cron.tick()
            self._drain_command_queue()
            self.engine.run_once(limit=10)
            time.sleep(interval_seconds)

    def _auto_enqueue_packs(self) -> None:
        now = datetime.now(timezone.utc)
        self._maybe_enqueue(
            "pack_lead_ops",
            now,
            interval_minutes=60,
            tasks=[
                {"type": "n8n.trigger", "payload": {"workflow": "openclaw-apify-ingest", "data": {}}},
                {"type": "n8n.trigger", "payload": {"workflow": "openclaw-retell-dispatch", "data": {}}},
                {"type": "n8n.trigger", "payload": {"workflow": "openclaw-nurture-run", "data": {}}},
            ],
        )
        self._maybe_enqueue(
            "pack_sales_intel",
            now,
            interval_minutes=1440,
            tasks=[{"type": "reports.daily", "payload": {}}],
        )

    def _maybe_enqueue(self, key: str, now: datetime, interval_minutes: int, tasks: Any) -> None:
        last = self._last_enqueued.get(key)
        if last and now - last < timedelta(minutes=interval_minutes):
            return
        for task in tasks:
            self.engine.enqueue(task["type"], task["payload"])
        self._last_enqueued[key] = now

    def trigger_graph_from_telegram(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Expected payload: {"graph": {...}, "context": {...}, "thread_name": "..."}."""
        graph = payload.get("graph")
        if not graph:
            raise RuntimeError("graph is required")
        thread_name = payload.get("thread_name") or "telegram"
        thread = self.context.create_thread(thread_name)
        # For now: store the request and return ack; execution handled via task.
        self.context.append_event(thread["id"], "telegram_graph_request", payload)
        return {"status": "queued", "thread_id": thread["id"]}

    def _load_command_queue_path(self) -> Optional[Path]:
        config_path = os.environ.get("OPENCLAW_CONFIG_PATH") or os.path.join(
            os.path.dirname(__file__), "..", "..", "openclaw.json"
        )
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            queue_file = config.get("paths", {}).get("commandQueueFile")
            if queue_file:
                return Path(queue_file)
        except FileNotFoundError:
            return None
        except json.JSONDecodeError:
            return None
        return None

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
        self._command_queue.write_text("", encoding="utf-8")
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
