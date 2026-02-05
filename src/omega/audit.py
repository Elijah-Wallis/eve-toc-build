from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class AuditReport:
    total_events: int
    triad_events: int
    last_24h_triad: int
    last_24h_events: int


def _parse_ts(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.now(timezone.utc)


def run_audit(ledger_path: str) -> AuditReport:
    path = Path(ledger_path)
    if not path.exists():
        return AuditReport(0, 0, 0, 0)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=1)

    total = 0
    triad = 0
    last_24h = 0
    last_24h_triad = 0

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = _parse_ts(event.get("ts", ""))
            if ts >= cutoff:
                last_24h += 1
            if event.get("event") == "triad_decision":
                triad += 1
                if ts >= cutoff:
                    last_24h_triad += 1

    return AuditReport(
        total_events=total,
        triad_events=triad,
        last_24h_triad=last_24h_triad,
        last_24h_events=last_24h,
    )
