#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from ontology.client import OntologyClient


ALLOWED_CATEGORIES = {"Medical spa", "Facial spa", "Day spa", "Health spa", "Spa"}


def normalize_phone(value: str) -> Optional[str]:
    digits = re.sub(r"[^0-9]", "", value or "")
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return None


def build_place_id(row: Dict[str, str], normalized_phone: str) -> str:
    source_url = row.get("url", "")
    if source_url:
        parsed = urlparse(source_url)
        q = parse_qs(parsed.query)
        place = (q.get("query_place_id") or [None])[0]
        if place:
            return place
    title = re.sub(r"[^a-z0-9]+", "-", (row.get("title", "") or "").strip().lower()).strip("-")
    phone_digits = re.sub(r"[^0-9]", "", normalized_phone)
    return f"csv-{title}-{phone_digits}"


def chunks(values: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Import MedSpa CSV into ontology-modeled leads table with strict filtering.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--campaign-tag", required=True)
    parser.add_argument("--report-file", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ontology = OntologyClient()

    path = Path(args.csv).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    stop_rows = ontology.select("stoplist", {"select": "phone"})
    stopset = {row.get("phone") for row in stop_rows if row.get("phone")}

    rows_total = 0
    excluded_non_medspa = 0
    invalid_phone = 0
    blocked_stoplist = 0
    dedup_dropped = 0

    dedup_by_phone: Dict[str, Dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows_total += 1
            category = (row.get("categoryName") or "").strip()
            if category not in ALLOWED_CATEGORIES:
                excluded_non_medspa += 1
                continue

            normalized_phone = normalize_phone(row.get("phone", ""))
            if not normalized_phone:
                invalid_phone += 1
                continue
            if normalized_phone in stopset:
                blocked_stoplist += 1
                continue
            if normalized_phone in dedup_by_phone:
                dedup_dropped += 1
                continue

            place_id = build_place_id(row, normalized_phone)
            dedup_by_phone[normalized_phone] = {
                "source": args.campaign_tag,
                "place_id": place_id,
                "business_name": (row.get("title") or "").strip(),
                "phone": normalized_phone,
                "email": None,
                "website": (row.get("website") or "").strip() or None,
                "address": (row.get("street") or "").strip() or None,
                "city": (row.get("city") or "").strip() or None,
                "state": (row.get("state") or "").strip() or None,
                "zip": None,
                "rating": float(row["totalScore"]) if (row.get("totalScore") or "").strip() else None,
                "reviews_count": int(float(row["reviewsCount"])) if (row.get("reviewsCount") or "").strip() else None,
                "categories": [category],
                "status": "NEW",
                "lead_type": "B2B",
                "decision_maker_confirmed": False,
                "positive_signal": False,
                "touch_count": 0,
                "paused_until": None,
            }

    accepted = list(dedup_by_phone.values())
    inserted_rows = 0
    if not args.dry_run and accepted:
        for batch in chunks(accepted, 200):
            for row in batch:
                upserted = ontology.insert("leads?on_conflict=place_id", row, return_representation=True)
                if upserted:
                    inserted_rows += 1

    result = {
        "csv": str(path),
        "campaign_tag": args.campaign_tag,
        "rows_total": rows_total,
        "accepted": len(accepted),
        "inserted_rows": inserted_rows,
        "excluded_non_medspa": excluded_non_medspa,
        "invalid_phone": invalid_phone,
        "blocked_stoplist": blocked_stoplist,
        "dedup_dropped": dedup_dropped,
        "dry_run": bool(args.dry_run),
    }
    if args.report_file:
        report_path = Path(args.report_file).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
