from __future__ import annotations

import json

from src.runtime.immutable_log import ImmutableLogWriter
from src.runtime.immutable_log import verify_log_chain
from src.runtime.telemetry import Telemetry


def test_telemetry_hash_chain_verifies(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENCLAW_IMMUTABLE_LOGS", "1")
    monkeypatch.setenv("OPENCLAW_IMMUTABLE_STRICT", "1")
    path = tmp_path / "telemetry.jsonl"
    telemetry = Telemetry(str(path))

    telemetry.emit("event_a", {"status": "ok"})
    telemetry.emit("event_b", {"status": "queued"})
    telemetry.emit("event_c", {"status": "completed"})

    report = verify_log_chain(path)
    assert report["ok"] is True
    assert report["record_count"] == 3
    assert report.get("errors") == []


def test_telemetry_hash_chain_detects_tamper(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENCLAW_IMMUTABLE_LOGS", "1")
    monkeypatch.setenv("OPENCLAW_IMMUTABLE_STRICT", "1")
    path = tmp_path / "telemetry.jsonl"
    telemetry = Telemetry(str(path))

    telemetry.emit("event_a", {"status": "ok"})
    telemetry.emit("event_b", {"status": "queued"})

    lines = path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[1])
    payload["status"] = "tampered"
    lines[1] = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = verify_log_chain(path)
    assert report["ok"] is False
    reasons = {err.get("reason") for err in report.get("errors", [])}
    assert "hash_mismatch" in reasons


def test_hash_chain_allows_legacy_interleaving_when_enabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENCLAW_IMMUTABLE_LOGS", "1")
    monkeypatch.setenv("OPENCLAW_IMMUTABLE_STRICT", "1")
    path = tmp_path / "telemetry.jsonl"
    telemetry = Telemetry(str(path))

    telemetry.emit("event_a", {"status": "ok"})
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": "2026-01-01T00:00:00+00:00", "event": "legacy_writer"}) + "\n")
    telemetry.emit("event_b", {"status": "ok"})

    strict_report = verify_log_chain(path)
    assert strict_report["ok"] is False

    compat_report = verify_log_chain(path, allow_legacy_interleaving=True)
    assert compat_report["ok"] is True
    assert compat_report["signed_record_count"] == 2


def test_hash_chain_is_stable_with_multiple_writers(tmp_path) -> None:
    path = tmp_path / "telemetry.jsonl"
    writer_a = ImmutableLogWriter(path, enabled=True, fsync_every=1)
    writer_b = ImmutableLogWriter(path, enabled=True, fsync_every=1)

    for idx in range(5):
        writer_a.append({"event": "a", "idx": idx})
        writer_b.append({"event": "b", "idx": idx})

    report = verify_log_chain(path)
    assert report["ok"] is True
    assert report["signed_record_count"] == 10
