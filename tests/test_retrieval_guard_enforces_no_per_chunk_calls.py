from __future__ import annotations

import pytest

from src.runtime.retrieval_guard import RetrievalCadenceGuard


def _attempt_retrieval_sequence(guard: RetrievalCadenceGuard, phases: list[str]) -> None:
    for phase in phases:
        guard.validate_phase(phase)  # raises on disallowed cadence


def test_retrieval_guard_enforces_no_per_chunk_calls() -> None:
    guard = RetrievalCadenceGuard()

    # Allowed once per turn or transcript milestone.
    _attempt_retrieval_sequence(guard, ["turn", "transcript_milestone"])

    # Simulated long generation where retrieval is attempted per chunk/token.
    with pytest.raises(RuntimeError, match="retrieval_cadence_violation_per_token_or_chunk"):
        _attempt_retrieval_sequence(guard, ["turn", "chunk", "chunk"])

    with pytest.raises(RuntimeError, match="retrieval_cadence_violation_per_token_or_chunk"):
        _attempt_retrieval_sequence(guard, ["turn", "token", "token"])
