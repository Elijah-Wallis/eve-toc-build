"""Runtime control plane for OpenClaw.

This package needs to be importable in clean CI environments. Avoid importing
runtime submodules at import time; expose a stable API via lazy attributes.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "ModelRouter",
    "ModelSpec",
    "TaskEngine",
    "TaskStatus",
    "TaskRegistry",
    "ContextStore",
    "SkillGraph",
    "SkillNode",
    "SkillExecutor",
    "Telemetry",
    "build_graph",
    "run_graph",
    "load_env_file",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "ModelRouter": (".model_router", "ModelRouter"),
    "ModelSpec": (".model_router", "ModelSpec"),
    "TaskEngine": (".task_engine", "TaskEngine"),
    "TaskStatus": (".task_engine", "TaskStatus"),
    "TaskRegistry": (".task_registry", "TaskRegistry"),
    "ContextStore": (".context_store", "ContextStore"),
    "SkillGraph": (".skill_graph", "SkillGraph"),
    "SkillNode": (".skill_graph", "SkillNode"),
    "SkillExecutor": (".skill_executor", "SkillExecutor"),
    "Telemetry": (".telemetry", "Telemetry"),
    "build_graph": (".graph_runner", "build_graph"),
    "run_graph": (".graph_runner", "run_graph"),
    "load_env_file": (".env_loader", "load_env_file"),
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

