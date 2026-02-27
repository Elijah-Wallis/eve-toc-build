from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def test_dashboard_js_files_parse() -> None:
    node = shutil.which("node")
    if not node:
        # Local dev machines will have node; CI or minimal runners may not.
        return

    repo = Path(__file__).resolve().parents[2]
    dash = repo / "dashboard"
    assert dash.exists()

    js_files = sorted([p for p in dash.rglob("*") if p.is_file() and p.suffix in {".js", ".mjs"}])
    assert js_files, "no dashboard JS files found"

    for p in js_files:
        proc = subprocess.run(
            [node, "--check", str(p)],
            text=True,
            capture_output=True,
            check=False,
        )
        assert proc.returncode == 0, f"node --check failed: {p}\n{proc.stderr}\n{proc.stdout}"

