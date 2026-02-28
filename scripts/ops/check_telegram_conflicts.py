#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List


TIMESTAMP_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T[0-9:.+\-Z]+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect sustained Telegram getUpdates conflicts.")
    parser.add_argument("--window-minutes", type=int, default=30)
    parser.add_argument("--max-conflicts", type=int, default=0)
    parser.add_argument(
        "--log-file",
        default=str(Path.home() / ".openclaw-eve" / "logs" / "gateway.err.log"),
    )
    return parser.parse_args()


def _parse_ts(line: str) -> datetime | None:
    match = TIMESTAMP_RE.search(line)
    if not match:
        return None
    raw = match.group("ts").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _conflicts_in_window(log_file: Path, window: timedelta) -> List[str]:
    if not log_file.exists():
        return []
    cutoff = datetime.now(timezone.utc) - window
    findings: List[str] = []
    for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "getUpdates conflict" not in line and "409: Conflict" not in line:
            continue
        ts = _parse_ts(line)
        if ts is None or ts.tzinfo is None:
            findings.append(line.strip())
            continue
        if ts >= cutoff:
            findings.append(line.strip())
    return findings


def _listener_count() -> int:
    try:
        out = subprocess.check_output(["ps", "aux"], text=True)
    except Exception:
        return 0
    return sum(1 for line in out.splitlines() if "src.runtime.telegram_listener" in line and "python" in line)


def main() -> int:
    args = parse_args()
    window = timedelta(minutes=max(1, args.window_minutes))
    log_file = Path(args.log_file).expanduser()
    conflicts = _conflicts_in_window(log_file, window)
    listener_count = _listener_count()
    report = {
        "ok": len(conflicts) <= args.max_conflicts and listener_count <= 1,
        "window_minutes": args.window_minutes,
        "conflict_count": len(conflicts),
        "listener_count": listener_count,
        "sample": conflicts[:10],
        "log_file": str(log_file),
    }
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
