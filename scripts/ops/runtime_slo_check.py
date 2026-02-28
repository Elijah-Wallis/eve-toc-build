#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.immutable_log import verify_log_chain


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check runtime telemetry against simple SLO thresholds.")
    parser.add_argument("--window-minutes", type=int, default=60)
    parser.add_argument("--max-errors", type=int, default=20)
    parser.add_argument("--telemetry-file", default=str(Path.home() / ".openclaw-eve" / "runtime" / "telemetry.jsonl"))
    parser.add_argument("--no-chain-check", action="store_true", help="Disable immutable hash-chain verification.")
    return parser.parse_args()


def _parse_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def main() -> int:
    args = parse_args()
    path = Path(args.telemetry_file).expanduser()
    records = _load_records(path)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, args.window_minutes))
    scoped = []
    for record in records:
        ts = _parse_ts(str(record.get("ts") or ""))
        if ts and ts >= cutoff:
            scoped.append(record)
    error_like = [
        row
        for row in scoped
        if "error" in str(row.get("event", "")).lower()
        or row.get("status") in {"error", "failed"}
        or "error" in row
    ]
    chain = {"ok": True, "record_count": len(records), "errors": []}
    if not args.no_chain_check:
        chain = verify_log_chain(path, max_errors=20, allow_legacy_prefix=True, allow_legacy_interleaving=True)

    overall_ok = len(error_like) <= args.max_errors and bool(chain.get("ok"))
    report = {
        "ok": overall_ok,
        "window_minutes": args.window_minutes,
        "max_errors": args.max_errors,
        "record_count": len(scoped),
        "error_count": len(error_like),
        "sample": error_like[:10],
        "telemetry_file": str(path),
        "chain": chain,
    }
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
