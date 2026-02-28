from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .runtime_paths import resolve_repo_root, resolve_state_dir as resolve_state_dir_from_runtime


ENV_ALIASES: Dict[str, tuple[str, ...]] = {
    "ANTHROPIC_API_KEY": ("ANTHORPIC_API_KEY",),
    "OPENCLAW_TELEGRAM_BOT_TOKEN": ("OPENCLAW_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"),
    "OPENCLAW_TELEGRAM_USER_ID": ("MY_TELEGRAM_ID",),
    "N8N_MCP_TOKEN": ("N8N_MCP_ACCESS_TOKEN",),
}


def apply_env_aliases() -> Dict[str, str]:
    """Populate canonical env keys from known aliases without overriding set values."""
    applied: Dict[str, str] = {}
    for canonical, aliases in ENV_ALIASES.items():
        if os.environ.get(canonical):
            continue
        for alias in aliases:
            value = os.environ.get(alias)
            if value:
                os.environ[canonical] = value
                applied[canonical] = alias
                break
    return applied


def resolve_state_dir() -> Path:
    return resolve_state_dir_from_runtime()


def resolve_runtime_dir() -> Path:
    return resolve_state_dir() / "runtime"


def resolve_telemetry_path() -> Path:
    raw = os.environ.get("OPENCLAW_TELEMETRY_PATH")
    if raw:
        return Path(os.path.expanduser(raw)).resolve()
    return resolve_runtime_dir() / "telemetry.jsonl"


def default_config_path() -> Path:
    env_path = os.environ.get("OPENCLAW_CONFIG_PATH")
    if env_path:
        return Path(os.path.expanduser(env_path)).resolve()
    return resolve_repo_root() / "openclaw.json"


def load_runtime_config(path: Optional[str] = None) -> Dict[str, Any]:
    config_path = Path(os.path.expanduser(path)).resolve() if path else default_config_path()
    if not config_path.exists():
        return {}
    try:
        content = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return adapt_legacy_config(content, config_path=config_path)


def adapt_legacy_config(config: Dict[str, Any], config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Translate a legacy repo-level config into a compatibility shape."""
    if not isinstance(config, dict):
        return {}
    out = dict(config)

    # v1 -> v2 model key migration for local runtime consumption.
    llm = out.get("llm") if isinstance(out.get("llm"), dict) else {}
    if llm and "provider" in llm and "agents" not in out:
        out["agents"] = {
            "defaults": {
                "model": {
                    "primary": llm.get("model") or "openrouter/moonshotai/kimi-k2.5",
                }
            }
        }

    # Normalize known path fields for portability.
    paths = out.get("paths") if isinstance(out.get("paths"), dict) else {}
    normalized_paths: Dict[str, Any] = {}
    for key, value in paths.items():
        normalized_paths[key] = _resolve_path(value, config_path=config_path)
    if normalized_paths:
        out["paths"] = normalized_paths

    # Canonical telegram env key for downstream runtime modules.
    skills = out.get("skills")
    if isinstance(skills, dict) and isinstance(skills.get("telegram"), dict):
        bot_env = skills["telegram"].get("botTokenEnv")
        if bot_env == "OPENCLAW_BOT_TOKEN":
            skills["telegram"]["botTokenEnv"] = "OPENCLAW_TELEGRAM_BOT_TOKEN"
            out["skills"] = skills
    return out


def resolve_command_queue_file(config_path: Optional[str] = None) -> Optional[Path]:
    config = load_runtime_config(path=config_path)
    paths = config.get("paths") if isinstance(config.get("paths"), dict) else {}
    queue_file = paths.get("commandQueueFile")
    if queue_file:
        return Path(str(queue_file)).resolve()
    # Fallback under runtime dir for portability.
    fallback = os.environ.get("OPENCLAW_COMMAND_QUEUE_FILE")
    if fallback:
        return Path(os.path.expanduser(fallback)).resolve()
    return resolve_runtime_dir() / "command_queue.txt"


def _resolve_path(value: Any, *, config_path: Optional[Path]) -> Any:
    if not isinstance(value, str) or not value:
        return value
    expanded = value
    expanded = expanded.replace("${REPO_ROOT}", str(resolve_repo_root()))
    expanded = expanded.replace("${OPENCLAW_STATE_DIR}", str(resolve_state_dir()))
    expanded = os.path.expandvars(expanded)
    if expanded.startswith("~"):
        return str(Path(os.path.expanduser(expanded)).resolve())
    path = Path(expanded)
    if path.is_absolute():
        return str(path)
    if config_path:
        return str((config_path.parent / path).resolve())
    return str(path.resolve())
