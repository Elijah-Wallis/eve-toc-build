from __future__ import annotations

from pathlib import Path

from scripts.ledger.verify_event_chain import verify_stream


def test_ledger_valid_chain_passes() -> None:
    result = verify_stream(Path("tests/fixtures/ledger/valid_chain.jsonl"))
    assert result["ok"] is True


def test_ledger_duplicate_event_id_fails() -> None:
    result = verify_stream(Path("tests/fixtures/ledger/invalid_duplicate_event_id.jsonl"))
    assert result["ok"] is False
    assert any(item["error"] == "duplicate_event_id" for item in result["failures"])


def test_ledger_prev_link_fails() -> None:
    result = verify_stream(Path("tests/fixtures/ledger/invalid_prev_link.jsonl"))
    assert result["ok"] is False
    assert any(item["error"] == "prev_link_missing" for item in result["failures"])
