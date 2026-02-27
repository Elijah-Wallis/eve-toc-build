#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

import requests


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _sb_headers() -> Dict[str, str]:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }


def _sb_base() -> str:
    base = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    if not base:
        raise RuntimeError("SUPABASE_URL is required")
    return base


def _fetch_rows(table: str, params: Dict[str, str], limit: int = 5000) -> List[Dict[str, Any]]:
    merged = dict(params)
    merged.setdefault("limit", str(limit))
    resp = requests.get(
        f"{_sb_base()}/rest/v1/{table}",
        headers=_sb_headers(),
        params=merged,
        timeout=45,
    )
    resp.raise_for_status()
    rows = resp.json()
    if not isinstance(rows, list):
        return []
    return rows


def _chunked(items: Iterable[str], size: int) -> Iterable[List[str]]:
    batch: List[str] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _fetch_lead_sources(lead_ids: Set[str]) -> Dict[str, str]:
    if not lead_ids:
        return {}
    out: Dict[str, str] = {}
    for batch in _chunked(sorted(lead_ids), 100):
        rows = _fetch_rows(
            "leads",
            {
                "select": "id,source",
                "id": f"in.({','.join(batch)})",
            },
            limit=100,
        )
        for row in rows:
            lead_id = str(row.get("id") or "")
            if lead_id:
                out[lead_id] = str(row.get("source") or "")
    return out


def _fetch_turn_counts(call_ids: Set[str]) -> Dict[str, int]:
    if not call_ids:
        return {}
    out: Dict[str, int] = {}
    for batch in _chunked(sorted(call_ids), 80):
        try:
            rows = _fetch_rows(
                "call_transcript_turns",
                {
                    "select": "retell_call_id,turn_index",
                    "retell_call_id": f"in.({','.join(batch)})",
                    "order": "turn_index.asc",
                },
                limit=10000,
            )
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                # Transcript tables may not be provisioned in older stacks.
                return {}
            raise
        for row in rows:
            call_id = str(row.get("retell_call_id") or "")
            idx = int(row.get("turn_index") or 0)
            out[call_id] = max(out.get(call_id, 0), idx + 1)
    return out


def _routing_success(outcome: str) -> bool:
    return str(outcome or "").upper() == "GRANTED"


def _human_answered(outcome: str) -> bool:
    return str(outcome or "").upper() != "VOICEMAIL"


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _cohort_metrics(rows: List[Dict[str, Any]], turn_counts: Dict[str, int]) -> Dict[str, Any]:
    total = len(rows)
    human_rows = [r for r in rows if _human_answered(str(r.get("outcome") or ""))]
    human_total = len(human_rows)
    routing_success_total = sum(1 for r in human_rows if _routing_success(str(r.get("outcome") or "")))
    gt4_turns = sum(1 for r in human_rows if turn_counts.get(str(r.get("retell_call_id") or ""), 0) > 4)

    outcome_breakdown: Dict[str, int] = {}
    for row in rows:
        key = str(row.get("outcome") or "PENDING").upper()
        outcome_breakdown[key] = outcome_breakdown.get(key, 0) + 1

    return {
        "total_calls": total,
        "human_answered_calls": human_total,
        "human_answered_share": _pct(human_total, total),
        "routing_success_calls": routing_success_total,
        "routing_success_rate": _pct(routing_success_total, human_total),
        "turn_count_gt4_calls": gt4_turns,
        "turn_count_gt4_rate": _pct(gt4_turns, human_total),
        "outcome_breakdown": outcome_breakdown,
    }


def _resolve_state_dir() -> Path:
    raw = os.environ.get("OPENCLAW_STATE_DIR", "")
    if raw.strip():
        return Path(os.path.expanduser(raw)).resolve()
    return (Path.home() / ".openclaw-eve").resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build V6 canary scorecard for TX B2B MedSpa cohort.")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--source-regex", default=r"^tx-medspa-")
    parser.add_argument("--min-human-answered", type=int, default=40)
    parser.add_argument("--output", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cutoff = _utc_now() - timedelta(hours=max(1, args.hours))
    source_re = re.compile(args.source_regex)

    sessions = _fetch_rows(
        "call_sessions",
        {
            "select": "id,lead_id,retell_call_id,agent_type,outcome,created_at",
            "retell_call_id": "not.is.null",
            "created_at": f"gte.{_iso(cutoff)}",
            "order": "created_at.desc",
        },
        limit=5000,
    )
    lead_ids = {str(r.get("lead_id") or "") for r in sessions if r.get("lead_id")}
    lead_source = _fetch_lead_sources(lead_ids)

    scoped: List[Dict[str, Any]] = []
    for row in sessions:
        lead_id = str(row.get("lead_id") or "")
        source = lead_source.get(lead_id, "")
        if not source_re.search(source):
            continue
        item = dict(row)
        item["source"] = source
        scoped.append(item)

    canary_rows = [r for r in scoped if str(r.get("agent_type") or "").upper() == "B2B_V6"]
    control_rows = [r for r in scoped if str(r.get("agent_type") or "").upper() in {"B2B", "B2B_OVERRIDE"}]

    call_ids = {str(r.get("retell_call_id") or "") for r in scoped if r.get("retell_call_id")}
    turn_counts = _fetch_turn_counts(call_ids)

    canary_metrics = _cohort_metrics(canary_rows, turn_counts)
    control_metrics = _cohort_metrics(control_rows, turn_counts)

    canary_lead_ids = {str(r.get("lead_id") or "") for r in canary_rows if r.get("lead_id")}
    control_lead_ids = {str(r.get("lead_id") or "") for r in control_rows if r.get("lead_id")}

    package_events = _fetch_rows(
        "lead_events",
        {
            "select": "lead_id,event_type,payload_json,created_at",
            "event_type": "eq.retell_evidence_package",
            "created_at": f"gte.{_iso(cutoff)}",
            "order": "created_at.desc",
        },
        limit=5000,
    )

    def _package_success(lead_ids_subset: Set[str]) -> Dict[str, Any]:
        relevant = [e for e in package_events if str(e.get("lead_id") or "") in lead_ids_subset]
        delivered = 0
        for event in relevant:
            payload = event.get("payload_json") or {}
            if isinstance(payload, dict) and str(payload.get("status") or "").lower() == "delivered":
                delivered += 1
        return {
            "attempts": len(relevant),
            "delivered": delivered,
            "delivery_success_rate": _pct(delivered, len(relevant)),
        }

    canary_package = _package_success(canary_lead_ids)
    control_package = _package_success(control_lead_ids)

    compliance_events = _fetch_rows(
        "lead_events",
        {
            "select": "id,event_type,lead_id,created_at",
            "event_type": "in.(compliance_incident,cpom_violation,retell_compliance_violation)",
            "created_at": f"gte.{_iso(cutoff)}",
        },
        limit=5000,
    )

    canary_routing = float(canary_metrics["routing_success_rate"])
    control_routing = float(control_metrics["routing_success_rate"])
    uplift = 0.0
    if control_routing > 0:
        uplift = round((canary_routing / control_routing) - 1.0, 4)

    human_answered_total = int(canary_metrics["human_answered_calls"]) + int(control_metrics["human_answered_calls"])
    gate = {
        "min_sample_met": human_answered_total >= int(args.min_human_answered),
        "routing_uplift_met": uplift >= 0.20,
        "compliance_clean": len(compliance_events) == 0,
        "promote_v6": False,
    }
    gate["promote_v6"] = bool(gate["min_sample_met"] and gate["routing_uplift_met"] and gate["compliance_clean"])

    report = {
        "status": "ok",
        "generated_at": _iso(_utc_now()),
        "window_hours": int(args.hours),
        "source_regex": args.source_regex,
        "cohorts": {
            "v6_canary": canary_metrics,
            "v5_control": control_metrics,
        },
        "delivery": {
            "v6_canary": canary_package,
            "v5_control": control_package,
        },
        "compliance_incident_count": len(compliance_events),
        "compliance_incidents": compliance_events[:50],
        "routing_uplift_relative": uplift,
        "promotion_gate": gate,
        "minimum_human_answered_required": int(args.min_human_answered),
    }

    if args.output:
        out_path = Path(args.output).expanduser().resolve()
    else:
        stamp = _utc_now().strftime("%Y%m%dT%H%M%SZ")
        out_path = _resolve_state_dir() / "runtime" / "reports" / f"v6_canary_scorecard_{stamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"ok": True, "report_path": str(out_path), "promotion_gate": gate}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
