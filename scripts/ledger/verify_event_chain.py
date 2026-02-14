#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


def verify_stream(path: Path) -> Dict[str, Any]:
    seen_ids: set[str] = set()
    last_version: Dict[str, int] = defaultdict(int)
    seen_by_entity: Dict[str, set[str]] = defaultdict(set)
    failures: List[Dict[str, Any]] = []

    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        event_id = str(row.get("event_id") or "").strip()
        entity = str(row.get("entity_key") or "").strip()
        schema_version = int(row.get("schema_version") or 0)

        if not event_id:
            failures.append({"line": line_no, "error": "missing_event_id"})
            continue
        if event_id in seen_ids:
            failures.append({"line": line_no, "event_id": event_id, "error": "duplicate_event_id"})
        seen_ids.add(event_id)

        if entity:
            prev_event_id = row.get("prev_event_id")
            if prev_event_id and prev_event_id not in seen_by_entity[entity]:
                failures.append(
                    {
                        "line": line_no,
                        "event_id": event_id,
                        "entity_key": entity,
                        "error": "prev_link_missing",
                        "prev_event_id": prev_event_id,
                    }
                )
            seen_by_entity[entity].add(event_id)

            if schema_version < last_version[entity]:
                failures.append(
                    {
                        "line": line_no,
                        "event_id": event_id,
                        "entity_key": entity,
                        "error": "schema_version_regression",
                        "previous": last_version[entity],
                        "current": schema_version,
                    }
                )
            last_version[entity] = max(last_version[entity], schema_version)

        event_type = str(row.get("event_type") or "").lower()
        if "shacl" in event_type:
            pointers = row.get("provenance_pointers")
            if not isinstance(pointers, list) or not pointers:
                failures.append(
                    {
                        "line": line_no,
                        "event_id": event_id,
                        "error": "missing_shacl_provenance_pointers",
                    }
                )

    return {
        "ok": len(failures) == 0,
        "failures": failures,
        "events_scanned": len(seen_ids),
        "path": str(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify immutable event chain invariants")
    parser.add_argument(
        "--input",
        default="tests/fixtures/ledger/valid_chain.jsonl",
        help="JSONL event stream path",
    )
    args = parser.parse_args()

    result = verify_stream(Path(args.input))
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
