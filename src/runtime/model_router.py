from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from ..omega.ledger import Ledger


@dataclass(frozen=True)
class ModelSpec:
    name: str
    provider: str
    max_context: int
    supports_tools: bool


class ModelRouter:
    """Resolve models with fallback, caps, and basic compatibility checks."""

    def __init__(self, ledger_path: Optional[str] = None) -> None:
        self._registry: Dict[str, ModelSpec] = {}
        self._load_defaults()
        self._ledger = Ledger(ledger_path) if ledger_path else None

    def _load_defaults(self) -> None:
        defaults = [
            ModelSpec("openrouter/auto", "openrouter", 200000, True),
            ModelSpec("openrouter/anthropic/claude-3.5-sonnet", "openrouter", 200000, True),
            ModelSpec("anthropic/claude-3-5-sonnet-20240620", "anthropic", 200000, True),
            ModelSpec("openai/gpt-4.1", "openai", 128000, True),
            ModelSpec("openai/gpt-4o", "openai", 128000, True),
        ]
        for spec in defaults:
            self._registry[spec.name] = spec

    def register(self, spec: ModelSpec) -> None:
        self._registry[spec.name] = spec

    def resolve(self, requested: str, provider: Optional[str] = None) -> ModelSpec:
        requested = (requested or "").strip()
        if requested in self._registry:
            return self._registry[requested]
        fallback = self._fallback_for(provider)
        spec = self._registry.get(fallback) or self._registry.get("openrouter/auto")
        if spec is None:
            spec = ModelSpec(requested or "unknown", provider or "unknown", 8192, False)
        self._log_event("model_fallback", {"requested": requested, "fallback": spec.name})
        return spec

    def pick(self, provider: Optional[str] = None) -> Tuple[ModelSpec, Dict[str, str]]:
        """Pick primary/fallback models from env with caps applied."""
        primary = os.environ.get("OPENROUTER_MODEL_PRIMARY") or os.environ.get("MODEL_PRIMARY")
        fallback = os.environ.get("OPENROUTER_MODEL_FALLBACK") or os.environ.get("MODEL_FALLBACK")
        if provider == "anthropic":
            fallback = fallback or os.environ.get("ANTHROPIC_MODEL_FALLBACK")
        spec = self.resolve(primary or "", provider)
        fallback_spec = self.resolve(fallback or "", provider)
        max_context = int(os.environ.get("MODEL_MAX_CONTEXT_TOKENS", spec.max_context))
        caps = {
            "max_context": str(max_context),
            "max_cost_usd": os.environ.get("MODEL_MAX_COST_USD_PER_RUN", ""),
        }
        if max_context < spec.max_context:
            spec = ModelSpec(spec.name, spec.provider, max_context, spec.supports_tools)
        self._log_event(
            "model_selection",
            {"primary": spec.name, "fallback": fallback_spec.name, "caps": caps},
        )
        return spec, caps

    def _fallback_for(self, provider: Optional[str]) -> str:
        if provider == "anthropic":
            return os.environ.get("ANTHROPIC_MODEL_FALLBACK", "anthropic/claude-3-5-sonnet-20240620")
        if provider == "openai":
            return os.environ.get("OPENAI_MODEL_FALLBACK", "openai/gpt-4o")
        return os.environ.get("OPENROUTER_MODEL_FALLBACK", "openrouter/anthropic/claude-3.5-sonnet")

    def _log_event(self, event: str, payload: Dict[str, object]) -> None:
        if not self._ledger:
            return
        self._ledger.append({"event": event, **payload})
