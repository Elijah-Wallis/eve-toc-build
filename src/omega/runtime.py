from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from .types import RiskClass, OmegaSkillInput
from .validator import OmegaValidator, ValidationError
from .lazarus import VisionAgent
from .ledger import Ledger
from .triad import TriadConsensus


class OmegaRuntimeError(RuntimeError):
    pass


@dataclass
class OmegaRuntime:
    """Protocol Omega runtime: triage + membrane + forge + lazarus + triad."""

    risk_class: RiskClass
    validator: Optional[OmegaValidator]
    vision_agent: VisionAgent
    ledger: Ledger
    triad: Optional[TriadConsensus] = None

    def _guard(self, input_data: OmegaSkillInput) -> None:
        # Code over conversation for safety checks
        if not input_data.entity_id:
            raise OmegaRuntimeError("entity_id is required")
        if not input_data.entity_name:
            raise OmegaRuntimeError("entity_name is required for Lazarus fallback")

    def execute(
        self,
        input_data: OmegaSkillInput,
        api_call: Callable[[OmegaSkillInput], Dict[str, Any]],
        vision_goal: Callable[[OmegaSkillInput], str],
        force_drift: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Execute the skill with stratified risk handling."""

        self._guard(input_data)

        # Phase 4: Triad (RiskClass A only)
        if self.risk_class == RiskClass.A:
            if self.triad is None:
                raise OmegaRuntimeError("Triad consensus required for RiskClass A")
            proposal_input = f"Action request for entity_id={input_data.entity_id} ({input_data.entity_name})"
            decision = self.triad.run(proposal_input)
            self.ledger.append({
                "event": "triad_decision",
                "approved": decision.approved,
                "proposal": decision.proposal,
                "audit": decision.audit,
                "signature": decision.signature,
            })
            if not decision.approved:
                raise OmegaRuntimeError("Triad denied request")

        # Phase 1+2: Membrane + Forge for B/A only
        if self.risk_class in (RiskClass.B, RiskClass.A):
            if self.validator is None:
                raise OmegaRuntimeError("Validator required for RiskClass B/A")
            self.validator.validate()

        # Phase 3: Lazarus fallback
        drift = input_data.force_drift if force_drift is None else force_drift
        try:
            if drift:
                raise ValidationError("Forced drift")
            return api_call(input_data)
        except (ValidationError, KeyError, ValueError) as err:
            self.ledger.append({
                "event": "drift_detected",
                "risk_class": self.risk_class.value,
                "error": str(err),
                "entity_id": input_data.entity_id,
            })
            goal = vision_goal(input_data)
            self.ledger.append({
                "event": "lazarus_engaged",
                "goal": goal,
                "entity_name": input_data.entity_name,
            })
            return self.vision_agent.execute_visually(goal=goal, context=input_data.context)
