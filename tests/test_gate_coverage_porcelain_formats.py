from __future__ import annotations

from types import SimpleNamespace

from src.runtime.proactive_review.analyzers import gate_coverage


def _analyze_dirty_status(dirty_status: str):
    ctx = SimpleNamespace(snapshot=SimpleNamespace(dirty_status=dirty_status))
    return gate_coverage.analyze(ctx)


def test_gate_coverage_parses_common_porcelain_formats() -> None:
    cases = [
        (" M src/runtime/__init__.py", "src/runtime/__init__.py"),
        ("M src/runtime/task_engine.py", "src/runtime/task_engine.py"),
        ("R  src/runtime/old.py -> src/runtime/new.py", "src/runtime/new.py"),
        ("C  src/runtime/a.py -> src/runtime/b.py", "src/runtime/b.py"),
        ("UU src/runtime/merge_conflict.py", "src/runtime/merge_conflict.py"),
        ("M src/runtime/file with spaces.py", "src/runtime/file with spaces.py"),
    ]

    for dirty_status, expected_path in cases:
        findings = _analyze_dirty_status(dirty_status)
        assert len(findings) == 1
        finding = findings[0]
        assert finding.category == "gate_coverage"
        assert expected_path in (finding.evidence or [])

