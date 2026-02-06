from __future__ import annotations

from typing import Any, Dict, Callable

from .context_store import ContextStore
from .skill_executor import SkillExecutor
from .skill_graph import SkillGraph, SkillNode
from .registry_defaults import handler_map


def build_graph(graph_def: Dict[str, Any]) -> SkillGraph:
    graph = SkillGraph()
    handlers = handler_map()
    for node_def in graph_def.get("nodes", []):
        handler_name = node_def.get("handler")
        handler: Callable[[Dict[str, Any]], Dict[str, Any]] = handlers.get(handler_name)
        if not handler:
            raise RuntimeError(f"Unknown handler {handler_name}")
        graph.add_node(
            SkillNode(
                name=node_def["name"],
                handler=handler,
                inputs=node_def.get("inputs", []),
                outputs=node_def.get("outputs", []),
                risk_class=node_def.get("risk_class", "C"),
                required_mcp=node_def.get("required_mcp", []),
                depends_on=node_def.get("depends_on", []),
            )
        )
    return graph


def run_graph(graph_def: Dict[str, Any], context: Dict[str, Any], thread_name: str, ledger_path: str) -> Dict[str, Any]:
    graph = build_graph(graph_def)
    store = ContextStore()
    thread = store.create_thread(thread_name)
    executor = SkillExecutor(graph, context=store, ledger_path=ledger_path)
    return executor.run(initial=context, thread_id=thread["id"])
