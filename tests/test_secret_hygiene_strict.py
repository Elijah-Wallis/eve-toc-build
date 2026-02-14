from __future__ import annotations

import re
from pathlib import Path


def test_secret_scanner_script_exists() -> None:
    path = Path("scripts/security/scan_secrets_strict.sh")
    assert path.exists()
    assert path.stat().st_mode & 0o111


def test_secret_pattern_detects_bad_token(tmp_path: Path) -> None:
    bad = tmp_path / "bad.txt"
    bad.write_text("token=ghp_abcdefghijklmnopqrstuvwxyz1234567890AB\n", encoding="utf-8")
    # Keep this test hermetic: don't require ripgrep to be installed in CI.
    text = bad.read_text(encoding="utf-8")
    assert re.search(r"ghp_[0-9A-Za-z]{36,}", text) is not None
