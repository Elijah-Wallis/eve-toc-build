#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCAN_DIRS = ("src", "services", "scripts", "policy")
TEXT_EXTENSIONS = {
    ".py",
    ".go",
    ".proto",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".sh",
    ".txt",
    ".ini",
    ".cfg",
    ".env",
}
FORBIDDEN_PATTERNS = {
    "mac_home_path": re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    "linux_home_path": re.compile(r"/home/[A-Za-z0-9._-]+/"),
    "windows_home_path": re.compile(r"C:\\\\Users\\\\[A-Za-z0-9._-]+\\\\"),
    "tilde_home_path": re.compile(r"(^|[^A-Za-z0-9_])~/"),
}


def _iter_files(scan_dirs: List[str]) -> List[Path]:
    files: List[Path] = []
    self_path = Path(__file__).resolve()
    for rel in scan_dirs:
        base = (ROOT / rel).resolve()
        if not base.exists() or not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.resolve() == self_path:
                continue
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            files.append(path)
    return files


def _runtime_generated_files() -> List[Path]:
    generated = (ROOT / "generated").resolve()
    if not generated.exists():
        return []
    files: List[Path] = []
    for path in generated.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if path.suffix.lower() not in {".json", ".yaml", ".yml", ".toml"}:
            continue
        # Scope to runtime/config-like artifacts to reduce noise from snapshots.
        if any(token in name for token in ("runtime", "config", "manifest", "policy")):
            files.append(path)
    return files


def _scan_file(path: Path) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings
    for line_no, line in enumerate(content.splitlines(), start=1):
        for key, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(line):
                findings.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "line": str(line_no),
                        "rule": key,
                        "snippet": line.strip()[:200],
                    }
                )
    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail if runtime code/config contains absolute home paths.")
    parser.add_argument(
        "--scan-dirs",
        default=",".join(DEFAULT_SCAN_DIRS),
        help="Comma-separated dirs relative to repo root.",
    )
    parser.add_argument("--allow-findings", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scan_dirs = [item.strip() for item in args.scan_dirs.split(",") if item.strip()]
    files = _iter_files(scan_dirs) + _runtime_generated_files()
    findings: List[Dict[str, str]] = []
    for path in files:
        findings.extend(_scan_file(path))
    report = {
        "ok": len(findings) == 0,
        "scanned_files": len(files),
        "finding_count": len(findings),
        "findings": findings[:500],
    }
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if findings and not args.allow_findings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
