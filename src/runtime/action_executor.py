from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .capability_tokens import CapabilityTokenStore
from .telemetry import Telemetry


class ActionExecutor:
    """
    Un-bypassable side-effect executor.

    All side effects must provide a valid firewall-issued capability token.
    """

    def __init__(self, token_store: CapabilityTokenStore, telemetry: Optional[Telemetry] = None) -> None:
        self.token_store = token_store
        self.telemetry = telemetry

    def execute(
        self,
        *,
        action: str,
        token: str,
        payload: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        grant = self.token_store.consume(token)
        if grant is None:
            self._emit("action_denied", action=action, reason="missing_or_expired_token")
            raise RuntimeError("action_denied_missing_or_expired_token")
        if grant.scope != action:
            self._emit("action_denied", action=action, reason="scope_mismatch")
            raise RuntimeError("action_denied_scope_mismatch")
        result = handler(payload)
        self._emit("action_executed", action=action, decision_id=grant.decision_id, status="ok")
        return result

    def _emit(self, event: str, **payload: Any) -> None:
        if self.telemetry is None:
            return
        self.telemetry.emit(event, payload)
