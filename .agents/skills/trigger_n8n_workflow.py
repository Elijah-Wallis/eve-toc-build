from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

import requests


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trigger n8n webhook workflow")
    parser.add_argument("--workflow", required=True, help="Webhook path")
    parser.add_argument("--payload", default="{}", help="JSON payload string")
    return parser.parse_args()


def _load_payload(raw: str) -> Dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError("payload must be valid JSON")


def main() -> int:
    args = _parse_args()
    base = os.environ.get("N8N_PUBLIC_WEBHOOK_BASE")
    if not base:
        raise RuntimeError("N8N_PUBLIC_WEBHOOK_BASE is not set")

    payload = _load_payload(args.payload)
    url = base.rstrip("/") + "/" + args.workflow.lstrip("/")
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    try:
        print(json.dumps(resp.json(), ensure_ascii=True))
    except ValueError:
        print(resp.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
