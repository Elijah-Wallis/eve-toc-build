from __future__ import annotations

from . import architecture_drift, code_quality, docs_drift, gate_coverage, performance_heuristics, repo_delta, repo_hygiene, security_hygiene

ANALYZERS_FAST = [
    repo_delta,
    repo_hygiene,
    security_hygiene,
    docs_drift,
    gate_coverage,
]

ANALYZERS_DEEP = [
    repo_delta,
    repo_hygiene,
    security_hygiene,
    docs_drift,
    gate_coverage,
    architecture_drift,
    performance_heuristics,
    code_quality,
]
