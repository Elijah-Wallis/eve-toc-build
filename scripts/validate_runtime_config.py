#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.config_adapter import (
    ENV_ALIASES,
    apply_env_aliases,
    default_config_path,
    load_runtime_config,
    resolve_command_queue_file,
    resolve_state_dir,
)


def main() -> int:
    config_path = default_config_path()
    config = load_runtime_config(str(config_path))
    aliases = apply_env_aliases()
    queue_file = resolve_command_queue_file(str(config_path))
    state_dir = resolve_state_dir()

    warnings = []
    if not config:
        warnings.append("config_unreadable_or_missing")
    if not queue_file:
        warnings.append("missing_command_queue_path")
    elif not str(queue_file).startswith("/"):
        warnings.append("command_queue_not_absolute")
    if not state_dir.exists():
        warnings.append("state_dir_missing")

    env_coverage = {}
    for canonical, alias_list in ENV_ALIASES.items():
        env_coverage[canonical] = {
            "set": bool(os.environ.get(canonical)),
            "aliases_present": [a for a in alias_list if os.environ.get(a)],
        }

    report = {
        "ok": len(warnings) == 0,
        "config_path": str(config_path),
        "state_dir": str(state_dir),
        "command_queue_file": str(queue_file) if queue_file else None,
        "applied_aliases": aliases,
        "env_coverage": env_coverage,
        "warnings": warnings,
    }
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
