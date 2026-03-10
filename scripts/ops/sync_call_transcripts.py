#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ontology.client import OntologyClient

from src.runtime.env_loader import load_env_file
from src.runtime.transcript_capture import normalize_call_payload, summarize_answerer


@dataclass
class SyncResult:
    retell_call_id: str
    campaign_tag: str
    business_name: str
    status: str
    turn_count: int
    outcome: str | None
    answerer: str
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync full Retell transcripts into Supabase transcript tables.")
    parser.add_argument("--campaign-tag", default="", help="Optional source filter, e.g. tx-medspa-2026-02-07")
    parser.add_argument("--lookback-hours", type=int, default=72)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repair-call-sessions", action="store_true", default=True)
    parser.add_argument("--report-file", default="", help="Optional JSON report path")
    parser.add_argument("--print-table", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env_file()

    ontology = OntologyClient(actor="sync-call-transcripts")
    retell_key = os.environ.get("RETELL_AI_KEY", "")
    retell_base = os.environ.get("RETELL_BASE_URL", "https://api.retellai.com").rstrip("/")
    if not retell_key:
        raise RuntimeError("RETELL_AI_KEY is required")
    rt_headers = {
        "Authorization": f"Bearer {retell_key}",
        "Content-Type": "application/json",
    }

    if not ontology.transcript_tables_enabled():
        raise RuntimeError(
            "Transcript tables are missing. Apply ${REPO_ROOT}/supabase/upgrade_transcripts.sql first."
        )

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, args.lookback_hours))
    call_sessions = _fetch_call_sessions(
        ontology=ontology,
        cutoff=cutoff,
        limit=max(1, args.limit),
    )
    if not call_sessions:
        report = {"ok": True, "count": 0, "results": []}
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0

    leads = _fetch_leads(ontology, [row["lead_id"] for row in call_sessions if row.get("lead_id")])
    lead_by_id = {row["id"]: row for row in leads if row.get("id")}

    filtered: List[Dict[str, Any]] = []
    for row in call_sessions:
        lead = lead_by_id.get(row.get("lead_id"), {})
        if args.campaign_tag and str(lead.get("source") or "") != args.campaign_tag:
            continue
        filtered.append(row)

    results: List[SyncResult] = []
    for row in filtered:
        call_id = str(row.get("retell_call_id") or "")
        if not call_id:
            continue
        lead = lead_by_id.get(row.get("lead_id"), {})
        try:
            payload = _fetch_retell_call(retell_base, rt_headers, call_id)
            record, turns = normalize_call_payload(payload, call_session=row, lead=lead)
            answerer = summarize_answerer(str(record.get("summary") or ""), str(record.get("transcript_text") or ""))
            if not args.dry_run:
                transcript_id = _upsert_transcript(ontology, record)
                _replace_turns(ontology=ontology, transcript_id=transcript_id, retell_call_id=call_id, turns=turns)
                if args.repair_call_sessions:
                    _repair_call_session(ontology, row, record)
            results.append(
                SyncResult(
                    retell_call_id=call_id,
                    campaign_tag=str(record.get("campaign_tag") or ""),
                    business_name=str(record.get("business_name") or ""),
                    status=str(record.get("retell_call_status") or ""),
                    turn_count=len(turns),
                    outcome=record.get("outcome"),
                    answerer=answerer,
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                SyncResult(
                    retell_call_id=call_id,
                    campaign_tag=str(lead.get("source") or ""),
                    business_name=str(lead.get("business_name") or ""),
                    status="error",
                    turn_count=0,
                    outcome=None,
                    answerer="unknown",
                    error=f"{type(exc).__name__}:{exc}",
                )
            )

    payload = {
        "ok": all(item.error is None for item in results),
        "dry_run": bool(args.dry_run),
        "count": len(results),
        "results": [item.__dict__ for item in results],
    }
    if args.report_file:
        with open(os.path.expanduser(args.report_file), "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True, indent=2) + "\n")
    if args.print_table:
        _print_table(results)
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload["ok"] else 2


def _fetch_call_sessions(
    *,
    ontology: OntologyClient,
    cutoff: datetime,
    limit: int,
) -> List[Dict[str, Any]]:
    params = {
        "select": "id,lead_id,retell_call_id,agent_type,created_at,outcome,summary,duration",
        "retell_call_id": "not.is.null",
        "created_at": f"gte.{cutoff.isoformat()}",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    return ontology.list_clinical_encounters(params)


def _fetch_leads(ontology: OntologyClient, lead_ids: Iterable[str]) -> List[Dict[str, Any]]:
    return ontology.list_patient_journeys_by_ids(
        lead_ids,
        select="id,source,business_name,phone,status,next_touch_at,last_contacted_at",
    )


def _fetch_retell_call(base_url: str, headers: Dict[str, str], retell_call_id: str) -> Dict[str, Any]:
    resp = requests.get(f"{base_url}/v2/get-call/{retell_call_id}", headers=headers, timeout=45)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError("Retell call response must be a JSON object")
    return data


def _upsert_transcript(ontology: OntologyClient, record: Dict[str, Any]) -> str:
    row = ontology.upsert_clinical_transcript(record)
    transcript_id = row.get("id") if isinstance(row, dict) else None
    if not transcript_id:
        raise RuntimeError("call_transcripts upsert did not return id")
    return str(transcript_id)


def _replace_turns(
    *,
    ontology: OntologyClient,
    transcript_id: str,
    retell_call_id: str,
    turns: List[Dict[str, Any]],
) -> None:
    rows = []
    for turn in turns:
        rows.append(
            {
                "transcript_id": transcript_id,
                "retell_call_id": retell_call_id,
                "turn_index": int(turn.get("turn_index", 0)),
                "speaker": str(turn.get("speaker") or "unknown"),
                "text": str(turn.get("text") or ""),
                "start_ms": turn.get("start_ms"),
                "end_ms": turn.get("end_ms"),
                "confidence": turn.get("confidence"),
                "payload_json": turn.get("payload_json") or {},
            }
        )
    ontology.replace_clinical_transcript_turns(transcript_id, retell_call_id, rows)


def _repair_call_session(
    ontology: OntologyClient,
    call_session: Dict[str, Any],
    transcript_record: Dict[str, Any],
) -> None:
    patch: Dict[str, Any] = {}
    if not call_session.get("outcome") and transcript_record.get("outcome"):
        patch["outcome"] = transcript_record["outcome"]
    if not call_session.get("summary") and transcript_record.get("summary"):
        patch["summary"] = transcript_record["summary"]
    if not call_session.get("duration") and transcript_record.get("duration_ms"):
        patch["duration"] = max(1, int(round(float(transcript_record["duration_ms"]) / 1000.0)))
    if not patch:
        return
    ontology.patch_clinical_encounter(str(call_session["id"]), patch)


def _print_table(results: List[SyncResult]) -> None:
    headers = ["retell_call_id", "campaign_tag", "business_name", "status", "outcome", "answerer", "turn_count", "error"]
    widths = {key: len(key) for key in headers}
    rows: List[Dict[str, str]] = []
    for item in results:
        row = {
            "retell_call_id": item.retell_call_id,
            "campaign_tag": item.campaign_tag,
            "business_name": item.business_name,
            "status": item.status,
            "outcome": item.outcome or "",
            "answerer": item.answerer,
            "turn_count": str(item.turn_count),
            "error": item.error or "",
        }
        rows.append(row)
        for key in headers:
            widths[key] = max(widths[key], len(row[key]))

    line = " | ".join(key.ljust(widths[key]) for key in headers)
    sep = "-+-".join("-" * widths[key] for key in headers)
    print(line)
    print(sep)
    for row in rows:
        print(" | ".join(row[key].ljust(widths[key]) for key in headers))


if __name__ == "__main__":
    raise SystemExit(main())
