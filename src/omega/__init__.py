"""Protocol Omega v4.0 — Pragmatic Skill Generation Workflow.

Avoid importing optional/heavy submodules at package import time. This keeps
`import src.omega.*` safe in clean CI and minimal runtimes.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "RiskClass",
    "OmegaSkillInput",
    "OmegaSkillSpec",
    "SessionVault",
    "OmegaHttpClient",
    "OmegaValidator",
    "ValidationError",
    "VisionAgent",
    "TriadConsensus",
    "TriadDecision",
    "Ledger",
    "run_audit",
    "AuditReport",
    "OmegaRuntime",
    "OmegaRuntimeError",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "RiskClass": (".types", "RiskClass"),
    "OmegaSkillInput": (".types", "OmegaSkillInput"),
    "OmegaSkillSpec": (".types", "OmegaSkillSpec"),
    "SessionVault": (".session_vault", "SessionVault"),
    "OmegaHttpClient": (".http_client", "OmegaHttpClient"),
    "OmegaValidator": (".validator", "OmegaValidator"),
    "ValidationError": (".validator", "ValidationError"),
    # VisionAgent depends on optional tooling (e.g., playwright). Keep it lazy.
    "VisionAgent": (".lazarus", "VisionAgent"),
    "TriadConsensus": (".triad", "TriadConsensus"),
    "TriadDecision": (".triad", "TriadDecision"),
    "Ledger": (".ledger", "Ledger"),
    "run_audit": (".audit", "run_audit"),
    "AuditReport": (".audit", "AuditReport"),
    "OmegaRuntime": (".runtime", "OmegaRuntime"),
    "OmegaRuntimeError": (".runtime", "OmegaRuntimeError"),
}


def __getattr__(name: str) -> Any:  # pragma: no cover
    spec = _LAZY_ATTRS.get(name)
    if not spec:
        raise AttributeError(name)
    module_name, attr = spec
    mod = import_module(module_name, __name__)
    return getattr(mod, attr)


def __dir__() -> list[str]:  # pragma: no cover
    return sorted(set(globals().keys()) | set(__all__))

