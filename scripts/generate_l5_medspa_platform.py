#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_SRC = REPO_ROOT / "platform"
if str(PLATFORM_SRC) not in sys.path:
    sys.path.insert(0, str(PLATFORM_SRC))

from l5_medspa_iac.generator import generate_platform_bundle
from l5_medspa_iac.generator import write_generation_result
from l5_medspa_iac.sandbox import build_sandbox_snapshot


def _load_spec(args: argparse.Namespace) -> str | dict[str, Any]:
    if args.spec_file:
        path = Path(args.spec_file)
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            return json.loads(text)
        return text
    if args.spec_text:
        return args.spec_text
    raise SystemExit("Either --spec-file or --spec-text is required")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a declarative EVE L5_Medspa_IaC platform bundle."
    )
    parser.add_argument("--spec-file", help="Path to JSON or text medspa client spec")
    parser.add_argument("--spec-text", help="Inline natural-language client spec")
    parser.add_argument(
        "--output-dir",
        default="platform/l5_medspa_iac/out",
        help="Directory where generated artifacts should be written",
    )
    parser.add_argument(
        "--sandbox-only",
        action="store_true",
        help="Write a sandbox snapshot in addition to the generated artifact bundle",
    )
    args = parser.parse_args()

    source = _load_spec(args)
    result = generate_platform_bundle(source)
    written = write_generation_result(result, args.output_dir)

    payload = {
        "status": "ok",
        "client_id": result.spec.client_id,
        "medspa_name": result.spec.medspa_name,
        "route": result.optimization.triage.route,
        "tier": result.optimization.triage.tier,
        "output_dir": str(Path(args.output_dir).resolve()),
        "written_files": [str(path) for path in written],
    }

    if args.sandbox_only:
        payload["sandbox"] = build_sandbox_snapshot(source, args.output_dir)

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
