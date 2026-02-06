from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class TaskHandler:
    name: str
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    idempotency_key: Optional[Callable[[Dict[str, Any]], str]] = None


class TaskRegistry:
    """Registry of task handlers keyed by task type."""

    def __init__(self) -> None:
        self._handlers: Dict[str, TaskHandler] = {}

    def register(self, task_type: str, handler: TaskHandler) -> None:
        self._handlers[task_type] = handler

    def get(self, task_type: str) -> Optional[TaskHandler]:
        return self._handlers.get(task_type)

    def list(self) -> Dict[str, TaskHandler]:
        return dict(self._handlers)
