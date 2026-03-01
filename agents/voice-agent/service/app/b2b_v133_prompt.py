"""
Load full V13.3 Emotional Resilience Inverter prompt from mcp_servers/b2b_workflow.yaml.

This content is the single source of truth for conversion-focused B2B voice. When using
custom LLM (BYOM), the voice-agent must use this exact prompt so behavior matches
Retell-hosted agent. Do not truncate or rewrite; only substitute runtime placeholders.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping


def load_b2b_v133_full_prompt(
    path: str | Path,
    *,
    placeholders: Mapping[str, str] | None = None,
) -> str:
    """
    Load the full b2b_workflow.yaml as system prompt (13k–15k tokens).
    Substitutes {{key}} with values from placeholders; unknown keys are left as-is.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"B2B V13.3 prompt file not found: {path}")
    raw = p.read_text(encoding="utf-8")
    subs = dict(placeholders or {})
    for key, value in subs.items():
        raw = raw.replace(f"{{{{{key}}}}}", str(value))
    return raw.strip()
