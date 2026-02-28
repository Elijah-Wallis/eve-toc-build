from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from src.runtime.postcall_reconciler import PostcallReconciler


class _FakeResponse:
    def __init__(self, status_code: int = 201, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http_{self.status_code}")

    def json(self) -> Any:
        return self._payload


def test_shacl_artifacts_e2e_invalid_payload_quarantined(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETELL_AI_KEY", "test-retell-key")
    reconciler = PostcallReconciler()

    session = {
        "id": "session-1",
        "lead_id": "lead-1",
        "retell_call_id": "call-1",
        "agent_type": "b2b",
        "outcome": None,
        "summary": None,
        "duration": None,
    }
    lead = {"id": "lead-1", "place_id": "place-1", "source": "tx-medspa"}

    monkeypatch.setattr(reconciler, "_fetch_call_sessions", lambda **_: [session])
    monkeypatch.setattr(reconciler, "_fetch_lead_map", lambda _: {"lead-1": lead})

    # Invalid ingest payload: deliberately missing summary/transcript fields.
    monkeypatch.setattr(reconciler, "_get_retell_call", lambda _: {"status": "completed"})

    monkeypatch.setattr(
        reconciler,
        "_patch_call_session_if_needed",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("must skip downstream mutation on validation failure")),
    )
    monkeypatch.setattr(
        reconciler,
        "_patch_lead_and_segment_if_needed",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("must skip downstream mutation on validation failure")),
    )
    monkeypatch.setattr(
        reconciler,
        "_upsert_postcall_event",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("must skip postcall event on validation failure")),
    )

    posted: Dict[str, List[Dict[str, Any]]] = {}

    def _fake_post(url: str, headers: Dict[str, str], data: str, timeout: int, params: Dict[str, Any] | None = None):
        table = url.rstrip("/").split("/")[-1]
        body = json.loads(data)
        posted.setdefault(table, []).append(body)
        return _FakeResponse(201, [body])

    monkeypatch.setattr("src.runtime.postcall_reconciler.requests.post", _fake_post)

    report = reconciler.reconcile({"lookback_hours": 1, "limit": 1, "unresolved_only": False})

    assert report["processed"] == 1
    assert report["quarantined_payloads"] == 1

    report_rows = posted.get("shacl_validation_reports", [])
    quarantine_rows = posted.get("ingest_quarantine", [])
    assert len(report_rows) == 1
    assert len(quarantine_rows) == 1

    validation_row = report_rows[0]
    quarantine_row = quarantine_rows[0]

    assert validation_row["event_id"] == "call-1-ingest"
    assert validation_row["report_schema_version"]
    assert validation_row["failure_code"] != "validation_failed"
    assert validation_row["missing_predicates"]
    assert validation_row["provenance_pointers"]

    assert quarantine_row["event_id"] == "call-1-ingest"
    assert quarantine_row["failure_code"] != "validation_failed"
    assert quarantine_row["missing_predicates"]
    assert quarantine_row["provenance_pointers"]
