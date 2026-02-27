from __future__ import annotations

from src.runtime.task_engine import TaskEngine
from src.runtime.task_registry import TaskRegistry


def test_lock_query_enforces_queued_state(monkeypatch) -> None:
    engine = TaskEngine(TaskRegistry())
    seen = {"table_query": ""}

    def fake_patch(table_query, patch, return_representation=False):  # noqa: ANN001
        seen["table_query"] = table_query
        return [
            {
                "id": "task-1",
                "type": "n8n.trigger",
                "payload_json": {},
                "retries": 0,
                "max_retries": 5,
            }
        ]

    monkeypatch.setattr(engine, "_patch", fake_patch)
    record = engine._lock_task({"id": "task-1"})  # noqa: SLF001
    assert record is not None
    assert "status=eq.queued" in seen["table_query"]
