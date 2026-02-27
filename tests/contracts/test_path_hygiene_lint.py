from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_no_absolute_home_paths_in_runtime_code_and_configs() -> None:
    cmd = [sys.executable, "scripts/ci/lint_no_absolute_paths.py"]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
