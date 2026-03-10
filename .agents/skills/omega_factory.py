from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run safe Eve self-improvement through the existing proposal system."
    )
    parser.add_argument("--mode", choices=["offline", "online"], default="offline")
    parser.add_argument("--profile", choices=["fast", "deep"], default="fast")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    cmd = [
        sys.executable,
        "-m",
        "src.runtime.proactive_review.daily_review",
        "--mode",
        args.mode,
        "--profile",
        args.profile,
        "--once",
    ]
    return subprocess.run(cmd, cwd=str(ROOT), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
