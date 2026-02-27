from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

from ..schemas import Finding


_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([a-zA-Z0-9_\.]+)", re.MULTILINE)


def _build_graph(py_files: List[Path], root: Path) -> Dict[str, Set[str]]:
    graph: Dict[str, Set[str]] = defaultdict(set)
    for file in py_files:
        rel = str(file.relative_to(root)).replace("/", ".")[:-3]
        text = file.read_text(encoding="utf-8", errors="ignore")
        for match in _IMPORT_RE.findall(text):
            if match.startswith("src."):
                graph[rel].add(match)
        graph.setdefault(rel, set())
    return graph


def _has_cycle(graph: Dict[str, Set[str]]) -> bool:
    visiting: Set[str] = set()
    visited: Set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in graph.get(node, set()):
            if nxt in graph and visit(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def analyze(ctx) -> List[Finding]:
    findings: List[Finding] = []
    py_files = list((ctx.repo_root / "src").rglob("*.py"))
    graph = _build_graph(py_files, ctx.repo_root)
    if _has_cycle(graph):
        findings.append(
            Finding(
                finding_id="arch-drift-import-cycle",
                title="Potential import cycle detected",
                category="architecture_drift",
                severity="medium",
                summary="Import graph suggests at least one module cycle in src/.",
                suggestion="Break cycle by moving shared interfaces/constants into dedicated modules.",
            )
        )
    hottest = sorted(graph.items(), key=lambda item: len(item[1]), reverse=True)[:5]
    ctx.report_sections["architecture_hotspots"] = [{"module": m, "fan_out": len(deps)} for m, deps in hottest]
    return findings
