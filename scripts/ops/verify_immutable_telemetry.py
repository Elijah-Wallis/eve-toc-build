#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.immutable_log import verify_log_chain


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify tamper-evident hash chain for runtime telemetry logs.")
    parser.add_argument(
        "--telemetry-file",
        default=str(Path.home() / ".openclaw-eve" / "runtime" / "telemetry.jsonl"),
        help="Path to immutable telemetry jsonl file.",
    )
    parser.add_argument("--max-errors", type=int, default=20)
    parser.add_argument("--allow-empty", action="store_true", help="Treat empty/missing log as pass.")
    parser.add_argument("--require-signed", action="store_true", help="Fail if no signed immutable records are present.")
    parser.add_argument(
        "--allow-legacy-interleaving",
        action="store_true",
        help="Allow unsigned legacy lines to appear between signed records.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.telemetry_file).expanduser()
    report = verify_log_chain(
        path,
        max_errors=max(1, args.max_errors),
        allow_legacy_prefix=True,
        allow_legacy_interleaving=bool(args.allow_legacy_interleaving),
        require_signed=bool(args.require_signed),
    )

    if args.allow_empty and report.get("record_count", 0) == 0:
        report["ok"] = True
        report["allow_empty"] = True
    report["telemetry_file"] = str(path)
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
