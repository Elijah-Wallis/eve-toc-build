from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict

from pydantic import BaseModel


class TriadDecision(BaseModel):
    proposal: str
    audit: str
    signature: str
    approved: bool


@dataclass
class TriadConsensus:
    """Triad consensus for RiskClass A."""

    llm_client: Callable[[str, str], str]

    def run(self, proposal_input: str) -> TriadDecision:
        # Eve: Proposal
        proposal = self.llm_client("eve", proposal_input)
        # Auditor: Policy check
        audit = self.llm_client("auditor", proposal)
        # Keymaster: Sign-off
        signature = self.llm_client("keymaster", audit)
        approved = "approve" in signature.lower()
        return TriadDecision(
            proposal=proposal,
            audit=audit,
            signature=signature,
            approved=approved,
        )
