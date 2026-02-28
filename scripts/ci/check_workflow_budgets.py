#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "policy" / "workflow_budgets.yaml"
REQUIRED_MARKERS = [
    "defaults:",
    "latency_ms:",
    "token_budget:",
    "coordination_ratio:",
    "safety:",
]


def main() -> int:
    findings = []
    if not POLICY.exists():
        findings.append({"kind": "missing_file", "path": str(POLICY.relative_to(ROOT))})
    else:
        text = POLICY.read_text(encoding="utf-8")
        for marker in REQUIRED_MARKERS:
            if marker not in text:
                findings.append({"kind": "missing_marker", "marker": marker})
    report = {"ok": len(findings) == 0, "file": str(POLICY.relative_to(ROOT)), "findings": findings}
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
