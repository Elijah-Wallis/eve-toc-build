#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ontology.client import OntologyClient  # noqa: E402
from src.runtime.env_loader import load_env_file  # noqa: E402


def _first_recording_url(ontology: OntologyClient) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "select": "id,retell_call_id,recording_url,created_at",
        "recording_url": "not.is.null",
        "order": "created_at.desc",
        "limit": "1",
    }
    rows = ontology.list_clinical_transcripts(params)
    return {"status_code": 200, "text": "", "json": rows}


def main() -> int:
    load_env_file()
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not supabase_key:
        report = {
            "ok": False,
            "error": "missing_env",
            "missing": [k for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY") if not os.environ.get(k)],
        }
        print(json.dumps(report, ensure_ascii=True))
        return 0

    result = _first_recording_url(OntologyClient(actor="dashboard-proof"))
    rows: List[Dict[str, Any]] = result["json"] or []
    sample: Optional[Dict[str, Any]] = rows[0] if rows else None

    ok = bool(sample and str(sample.get("recording_url") or "").strip())
    report = {
        "ok": ok,
        "status_code": result["status_code"],
        "has_recording_url_row": bool(sample),
        "sample_retell_call_id": (sample or {}).get("retell_call_id"),
        "sample_recording_url": (sample or {}).get("recording_url"),
    }
    if not ok and result["status_code"] != 200:
        report["error"] = "http_error"
        report["details"] = (result.get("text") or "")[:200]
    elif not ok:
        report["error"] = "no_nonnull_recording_url_rows"

    print(json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
