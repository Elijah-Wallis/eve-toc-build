from __future__ import annotations

from src.runtime.proactive_review.daily_review import evaluate_proposal_quality
from src.runtime.proactive_review.schemas import ProposalCandidate


def _candidate() -> ProposalCandidate:
    return ProposalCandidate(
        proposal_id="p-1",
        title="test",
        category="x",
        why="why",
        risk_tier="A",
        impact=1,
        effort=1,
        risk=1,
        confidence=0,
        testability=1,
        validation_ids=[],
        rollback_plan="",
        blast_radius_files=[],
    )


def test_quality_marks_incomplete_and_penalizes() -> None:
    c = _candidate()
    penalty = evaluate_proposal_quality(c)
    assert penalty < 0
    assert c.quality_label == "INCOMPLETE — NOT READY"
    assert "missing_validation_ids" in c.quality_issues
