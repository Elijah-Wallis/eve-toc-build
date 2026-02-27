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

    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    retell_key = os.environ.get("RETELL_AI_KEY", "")
    retell_base = os.environ.get("RETELL_BASE_URL", "https://api.retellai.com").rstrip("/")
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    if not retell_key:
        raise RuntimeError("RETELL_AI_KEY is required")

    sb_headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }
    rt_headers = {
        "Authorization": f"Bearer {retell_key}",
        "Content-Type": "application/json",
    }

    if not _table_exists(supabase_url, sb_headers, "call_transcripts"):
        raise RuntimeError(
            "call_transcripts table is missing. Apply ${REPO_ROOT}/supabase/upgrade_transcripts.sql first."
        )
    if not _table_exists(supabase_url, sb_headers, "call_transcript_turns"):
        raise RuntimeError(
            "call_transcript_turns table is missing. Apply ${REPO_ROOT}/supabase/upgrade_transcripts.sql first."
        )

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, args.lookback_hours))
    call_sessions = _fetch_call_sessions(
        supabase_url=supabase_url,
        headers=sb_headers,
        cutoff=cutoff,
        limit=max(1, args.limit),
    )
    if not call_sessions:
        report = {"ok": True, "count": 0, "results": []}
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0

    leads = _fetch_leads(supabase_url, sb_headers, [row["lead_id"] for row in call_sessions if row.get("lead_id")])
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
                transcript_id = _upsert_transcript(supabase_url, sb_headers, record)
                _replace_turns(
                    supabase_url=supabase_url,
                    headers=sb_headers,
                    transcript_id=transcript_id,
                    retell_call_id=call_id,
                    turns=turns,
                )
                if args.repair_call_sessions:
                    _repair_call_session(supabase_url, sb_headers, row, record)
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


def _table_exists(supabase_url: str, headers: Dict[str, str], table: str) -> bool:
    resp = requests.get(
        f"{supabase_url}/rest/v1/{table}",
        headers=headers,
        params={"select": "id", "limit": "1"},
        timeout=20,
    )
    if resp.status_code == 404:
        return False
    resp.raise_for_status()
    return True


def _fetch_call_sessions(
    *,
    supabase_url: str,
    headers: Dict[str, str],
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
    resp = requests.get(
        f"{supabase_url}/rest/v1/call_sessions",
        headers=headers,
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_leads(supabase_url: str, headers: Dict[str, str], lead_ids: Iterable[str]) -> List[Dict[str, Any]]:
    ids = [str(item) for item in lead_ids if item]
    if not ids:
        return []
    records: List[Dict[str, Any]] = []
    for offset in range(0, len(ids), 120):
        batch = ids[offset : offset + 120]
        params = {
            "select": "id,source,business_name,phone,status,next_touch_at,last_contacted_at",
            "id": f"in.({','.join(batch)})",
        }
        resp = requests.get(
            f"{supabase_url}/rest/v1/leads",
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        records.extend(resp.json())
    return records


def _fetch_retell_call(base_url: str, headers: Dict[str, str], retell_call_id: str) -> Dict[str, Any]:
    resp = requests.get(f"{base_url}/v2/get-call/{retell_call_id}", headers=headers, timeout=45)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError("Retell call response must be a JSON object")
    return data


def _upsert_transcript(supabase_url: str, headers: Dict[str, str], record: Dict[str, Any]) -> str:
    write_headers = dict(headers)
    write_headers["Prefer"] = "return=representation,resolution=merge-duplicates"
    resp = requests.post(
        f"{supabase_url}/rest/v1/call_transcripts",
        headers=write_headers,
        params={"on_conflict": "retell_call_id"},
        data=json.dumps(record),
        timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json()
    row = rows[0] if isinstance(rows, list) and rows else rows
    transcript_id = row.get("id") if isinstance(row, dict) else None
    if not transcript_id:
        raise RuntimeError("call_transcripts upsert did not return id")
    return str(transcript_id)


def _replace_turns(
    *,
    supabase_url: str,
    headers: Dict[str, str],
    transcript_id: str,
    retell_call_id: str,
    turns: List[Dict[str, Any]],
) -> None:
    delete_resp = requests.delete(
        f"{supabase_url}/rest/v1/call_transcript_turns",
        headers=headers,
        params={"transcript_id": f"eq.{transcript_id}"},
        timeout=20,
    )
    delete_resp.raise_for_status()
    if not turns:
        return

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

    write_headers = dict(headers)
    write_headers["Prefer"] = "return=minimal"
    for offset in range(0, len(rows), 500):
        batch = rows[offset : offset + 500]
        insert_resp = requests.post(
            f"{supabase_url}/rest/v1/call_transcript_turns",
            headers=write_headers,
            data=json.dumps(batch),
            timeout=30,
        )
        insert_resp.raise_for_status()


def _repair_call_session(
    supabase_url: str,
    headers: Dict[str, str],
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
    resp = requests.patch(
        f"{supabase_url}/rest/v1/call_sessions",
        headers=headers,
        params={"id": f"eq.{call_session['id']}"},
        data=json.dumps(patch),
        timeout=20,
    )
    resp.raise_for_status()


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
