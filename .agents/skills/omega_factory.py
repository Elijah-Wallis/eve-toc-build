from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from omega.factory import OmegaSkillFactory
from omega.types import OmegaSkillSpec, RiskClass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Protocol Omega Skill Factory")
    parser.add_argument("--name", required=True)
    parser.add_argument("--risk", required=True, choices=["A", "B", "C"])
    parser.add_argument("--openapi", required=True)
    parser.add_argument("--test-event", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--description", default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    spec = OmegaSkillSpec(
        name=args.name,
        risk_class=RiskClass(args.risk),
        openapi_path=args.openapi,
        test_event_path=args.test_event,
        output_dir=args.output_dir,
        description=args.description,
    )
    target = OmegaSkillFactory().generate(spec)
    print(f"Generated: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
