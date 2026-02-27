#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.env_loader import load_env_file
from src.runtime.postcall_reconciler import PostcallReconciler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run immediate Retell post-call reconciliation.")
    parser.add_argument("--campaign-tag", default="")
    parser.add_argument("--lookback-hours", type=int, default=96)
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-transcripts", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env_file()
    reconciler = PostcallReconciler()
    report = reconciler.reconcile(
        {
            "campaign_tag": args.campaign_tag.strip(),
            "lookback_hours": args.lookback_hours,
            "limit": args.limit,
            "unresolved_only": not args.force,
            "force": bool(args.force),
            "write_transcripts": not args.no_transcripts,
        }
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
