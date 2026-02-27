from __future__ import annotations

import pytest

from src.runtime.retrieval_guard import RetrievalCadenceGuard


def test_retrieval_guard_allows_turn_and_milestone() -> None:
    guard = RetrievalCadenceGuard()
    guard.validate_phase("turn")
    guard.validate_phase("transcript_milestone")


def test_retrieval_guard_blocks_token_and_chunk() -> None:
    guard = RetrievalCadenceGuard()
    with pytest.raises(RuntimeError):
        guard.validate_phase("token")
    with pytest.raises(RuntimeError):
        guard.validate_phase("chunk")
