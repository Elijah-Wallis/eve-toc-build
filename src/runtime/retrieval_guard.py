from __future__ import annotations

from typing import Literal


RetrievalPhase = Literal["turn", "transcript_milestone", "token", "chunk", "unknown"]


class RetrievalCadenceGuard:
    """
    Enforces retrieval cadence policy for ontology kernel access.

    Policy:
    - Allowed: per-turn, transcript milestone.
    - Forbidden: per-token, per-chunk.
    """

    def validate_phase(self, phase: RetrievalPhase) -> None:
        normalized = str(phase or "unknown").strip().lower()
        if normalized in {"token", "chunk"}:
            raise RuntimeError("retrieval_cadence_violation_per_token_or_chunk")
