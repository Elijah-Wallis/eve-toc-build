from __future__ import annotations

from typing import Any, Dict, Optional

from ..omega.ledger import Ledger

from .context_store import ContextStore
from .skill_graph import SkillGraph


class SkillExecutor:
    """Execute a skill graph with context logging."""

    def __init__(self, graph: SkillGraph, context: Optional[ContextStore] = None, ledger_path: Optional[str] = None) -> None:
        self.graph = graph
        self.context = context
        self.ledger = Ledger(ledger_path) if ledger_path else None

    def run(self, initial: Dict[str, Any], thread_id: Optional[str] = None) -> Dict[str, Any]:
        data: Dict[str, Any] = dict(initial)
        for node in self.graph.order():
            result = node.handler(data)
            data.update(result)
            if self.context and thread_id:
                self.context.append_event(thread_id, f"skill.{node.name}", {"input": data, "output": result})
            if self.ledger:
                self.ledger.append({"event": "skill_run", "node": node.name, "result": result})
        return data
