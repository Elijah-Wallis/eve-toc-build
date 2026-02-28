from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _base_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    runtime_dir = state_dir / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    command_queue = runtime_dir / "command_queue.txt"
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(
        '{"paths":{"commandQueueFile":"' + str(command_queue) + '"}}',
        encoding="utf-8",
    )

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.local")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    monkeypatch.setenv("N8N_PUBLIC_WEBHOOK_BASE", "https://example.n8n.local")
    monkeypatch.setenv("N8N_API_BASE", "https://example.n8n.local/api/v1")
    monkeypatch.setenv("N8N_API_KEY", "test-n8n-api-key")
    monkeypatch.setenv("OPENCLAW_CAPTURE_TRAFFIC", "0")
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(state_dir))
    monkeypatch.setenv("OPENCLAW_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("OPENCLAW_COMMAND_QUEUE_FILE", str(command_queue))
    monkeypatch.setenv("OPENCLAW_RUNTIME_STABILITY_ENVELOPE", "1")
    monkeypatch.setenv("OPENCLAW_STEP_MAX_RETRIES", "1")
    monkeypatch.setenv("OPENCLAW_STEP_BACKOFF_MS", "1")
    monkeypatch.setenv("OPENCLAW_FATAL_ERROR_BUDGET_PER_HOUR", "100")
    monkeypatch.setenv("OPENCLAW_OUTBOX_EMIT", "0")
