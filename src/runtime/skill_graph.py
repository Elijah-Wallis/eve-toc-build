from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class SkillNode:
    name: str
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    risk_class: str = "C"
    required_mcp: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)


class SkillGraph:
    """Directed acyclic graph of skills."""

    def __init__(self) -> None:
        self._nodes: Dict[str, SkillNode] = {}

    def add_node(self, node: SkillNode) -> None:
        if node.name in self._nodes:
            raise ValueError(f"duplicate node {node.name}")
        self._nodes[node.name] = node

    def nodes(self) -> Dict[str, SkillNode]:
        return dict(self._nodes)

    def order(self) -> List[SkillNode]:
        visited = set()
        temp = set()
        result: List[SkillNode] = []

        def visit(name: str) -> None:
            if name in temp:
                raise ValueError("cycle detected")
            if name in visited:
                return
            temp.add(name)
            node = self._nodes.get(name)
            if not node:
                raise KeyError(f"missing node {name}")
            for dep in node.depends_on:
                visit(dep)
            temp.remove(name)
            visited.add(name)
            result.append(node)

        for name in self._nodes:
            visit(name)
        return result
