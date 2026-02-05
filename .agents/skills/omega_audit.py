from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from omega.audit import run_audit


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Protocol Omega daily audit")
    parser.add_argument(
        "--ledger",
        default=str(Path.home() / ".openclaw-eve" / "omega" / "ledger.jsonl"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_audit(args.ledger)
    print(
        "AuditReport: total={total} triad={triad} last24h={last24h} last24h_triad={last24h_triad}".format(
            total=report.total_events,
            triad=report.triad_events,
            last24h=report.last_24h_events,
            last24h_triad=report.last_24h_triad,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
