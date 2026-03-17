#!/usr/bin/env python3
"""Compatibility shim delegating to the Rust validator."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    cmd = ["cargo", "run", "--quiet", "--", "validate-runtime-config"]
    env = dict(os.environ)
    proc = subprocess.run(cmd, cwd=repo_root, env=env)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
