#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[2]

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"),  # Telegram token shape
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}", re.IGNORECASE),
]

ALLOWLIST_PATHS = {
    ".env.example",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan repo and process surfaces for secret exposure.")
    parser.add_argument("--allow-findings", action="store_true")
    parser.add_argument(
        "--allow-process-args",
        action="store_true",
        help="Do not fail the scan solely due to secret-like patterns in running process argv. Repo findings still fail.",
    )
    return parser.parse_args()


def _tracked_files() -> List[Path]:
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [ROOT / line.strip() for line in out.splitlines() if line.strip()]


def _scan_repo() -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    for path in _tracked_files():
        rel = str(path.relative_to(ROOT))
        if rel in ALLOWLIST_PATHS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in SECRET_PATTERNS):
                findings.append({"surface": "repo", "path": rel, "line": str(idx)})
                if len(findings) >= 200:
                    return findings
    return findings


def _scan_process_args() -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    try:
        out = subprocess.check_output(["ps", "aux"], text=True)
    except Exception:
        return findings
    for line in out.splitlines():
        if "ps aux" in line:
            continue
        if any(pattern.search(line) for pattern in SECRET_PATTERNS):
            findings.append({"surface": "process_args", "sample": line[:220]})
    return findings


def main() -> int:
    args = parse_args()
    repo_findings = _scan_repo()
    proc_findings = _scan_process_args()
    findings = repo_findings + proc_findings
    ok = (len(repo_findings) == 0) and (len(proc_findings) == 0 or bool(args.allow_process_args))
    report = {
        "ok": ok,
        "counts": {
            "repo": len(repo_findings),
            "process_args": len(proc_findings),
            "total": len(findings),
        },
        "allow_process_args": bool(args.allow_process_args),
        "findings": findings[:50],
    }
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if not ok and not args.allow_findings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
