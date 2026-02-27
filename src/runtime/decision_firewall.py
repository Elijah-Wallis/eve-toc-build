from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .capability_tokens import CapabilityTokenStore
from .telemetry import Telemetry


HIGH_STAKES_ACTIONS = {
    "treatment_plan_change",
    "eligibility_decision",
    "dosing_change",
    "procedure_parameter_change",
    "contraindication_override",
    "clinical_escalation_decision",
}


@dataclass(frozen=True)
class DecisionResult:
    decision_id: str
    allowed: bool
    risk_tier: int
    requires_clinician_review: bool
    failure_code: Optional[str]
    missing_predicates: List[str]
    provenance_pointers: List[str]


class DecisionFirewall:
    """
    Risk-tiered decision firewall.

    Architectural contract:
    - Audit decision event first.
    - Issue scoped short-lived token only when action is allowed by policy.
    """

    def __init__(self, telemetry: Optional[Telemetry] = None, token_store: Optional[CapabilityTokenStore] = None) -> None:
        self.telemetry = telemetry
        self.tokens = token_store or CapabilityTokenStore()

    def evaluate(self, action: str, payload: Dict[str, Any]) -> DecisionResult:
        decision_id = f"dec_{uuid.uuid4().hex[:16]}"
        requested_tier = int(payload.get("risk_tier", 0) or 0)
        risk_tier = max(0, min(3, requested_tier))
        missing_predicates = [str(x) for x in (payload.get("missing_predicates") or []) if str(x).strip()]
        provenance_pointers = [str(x) for x in (payload.get("provenance_pointers") or []) if str(x).strip()]
        high_stakes = action in HIGH_STAKES_ACTIONS or risk_tier >= 3

        if high_stakes:
            result = DecisionResult(
                decision_id=decision_id,
                allowed=False,
                risk_tier=3,
                requires_clinician_review=True,
                failure_code="clinician_gate_required",
                missing_predicates=missing_predicates,
                provenance_pointers=provenance_pointers,
            )
            self._emit_decision(result, action=action, payload=payload)
            return result

        if missing_predicates:
            result = DecisionResult(
                decision_id=decision_id,
                allowed=False,
                risk_tier=max(1, risk_tier),
                requires_clinician_review=True,
                failure_code="missing_evidence",
                missing_predicates=missing_predicates,
                provenance_pointers=provenance_pointers,
            )
            self._emit_decision(result, action=action, payload=payload)
            return result

        result = DecisionResult(
            decision_id=decision_id,
            allowed=True,
            risk_tier=risk_tier,
            requires_clinician_review=False,
            failure_code=None,
            missing_predicates=[],
            provenance_pointers=provenance_pointers,
        )
        self._emit_decision(result, action=action, payload=payload)
        return result

    def issue_capability_token(self, *, decision: DecisionResult, action_scope: str, ttl_seconds: int = 120) -> str:
        if not decision.allowed:
            raise RuntimeError("capability_token_denied")
        grant = self.tokens.issue(decision_id=decision.decision_id, scope=action_scope, ttl_seconds=ttl_seconds)
        if self.telemetry is not None:
            self.telemetry.emit(
                "firewall_capability_issued",
                {
                    "decision_id": decision.decision_id,
                    "scope": action_scope,
                    "ttl_seconds": int(ttl_seconds),
                },
            )
        return grant.token

    def _emit_decision(self, result: DecisionResult, *, action: str, payload: Dict[str, Any]) -> None:
        if self.telemetry is None:
            return
        self.telemetry.emit(
            "firewall_decision",
            {
                "decision_id": result.decision_id,
                "action": action,
                "allowed": result.allowed,
                "risk_tier": result.risk_tier,
                "requires_clinician_review": result.requires_clinician_review,
                "failure_code": result.failure_code,
                "missing_predicates": result.missing_predicates,
                "provenance_pointers": result.provenance_pointers,
                "payload_keys": sorted(payload.keys()),
            },
        )
