from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import requests

from .ingest_validator import build_persistence_records
from .ingest_validator import validate_retell_payload
from .telemetry import Telemetry
from .transcript_capture import normalize_call_payload


OUTCOME_STATUS_MAP = {
    "GRANTED": "QUALIFIED",
    "STALLED": "NURTURE",
    "REVOKED": "DNC",
    "VOICEMAIL": "RETRY",
    "GATEKEEPER": "HOLD",
}


class PostcallReconciler:
    def __init__(self, telemetry: Optional[Telemetry] = None) -> None:
        self.telemetry = telemetry
        self.supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.retell_base = os.environ.get("RETELL_BASE_URL", "https://api.retellai.com").rstrip("/")
        self.retell_key = os.environ.get("RETELL_AI_KEY", "")
        if not self.supabase_url or not self.supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        if not self.retell_key:
            raise RuntimeError("RETELL_AI_KEY is required")
        self._transcript_tables_available: Optional[bool] = None

    def reconcile(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        args = dict(payload or {})
        lookback_hours = max(1, int(args.get("lookback_hours", 72)))
        limit = max(1, min(2000, int(args.get("limit", 400))))
        unresolved_only = bool(args.get("unresolved_only", True))
        campaign_tag = str(args.get("campaign_tag") or "").strip()
        force = bool(args.get("force", False))
        write_transcripts = bool(args.get("write_transcripts", True))

        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        sessions = self._fetch_call_sessions(cutoff=cutoff, limit=limit)
        if unresolved_only and not force:
            sessions = [row for row in sessions if self._session_needs_repair(row)]

        lead_map = self._fetch_lead_map([row.get("lead_id") for row in sessions if row.get("lead_id")])

        processed = 0
        repaired_sessions = 0
        repaired_leads = 0
        inserted_events = 0
        inserted_transcripts = 0
        quarantined_payloads = 0
        errors: List[Dict[str, Any]] = []

        for session in sessions:
            lead = lead_map.get(str(session.get("lead_id") or ""), {})
            if campaign_tag and str(lead.get("source") or "") != campaign_tag:
                continue
            call_id = str(session.get("retell_call_id") or "")
            if not call_id:
                continue
            processed += 1
            try:
                retell_payload = self._get_retell_call(call_id)
                validation_failure = validate_retell_payload(
                    payload=retell_payload,
                    event_id=f"{call_id}-ingest",
                    provenance_pointers=[
                        f"retell_call:{call_id}",
                        f"call_session:{session.get('id')}",
                    ],
                )
                if validation_failure:
                    self._persist_validation_failure(validation_failure)
                    quarantined_payloads += 1
                    continue
                record, turns = normalize_call_payload(retell_payload, call_session=session, lead=lead)
                if self._patch_call_session_if_needed(session, record, force=force):
                    repaired_sessions += 1
                if self._patch_lead_and_segment_if_needed(lead, record, force=force):
                    repaired_leads += 1
                if self._upsert_postcall_event(session, lead, retell_payload):
                    inserted_events += 1
                if write_transcripts and self._transcript_tables_enabled():
                    self._upsert_transcript_and_turns(record, turns)
                    inserted_transcripts += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    {
                        "retell_call_id": call_id,
                        "lead_id": session.get("lead_id"),
                        "error": f"{type(exc).__name__}:{exc}",
                    }
                )

        report = {
            "status": "ok" if not errors else "degraded",
            "processed": processed,
            "repaired_sessions": repaired_sessions,
            "repaired_leads": repaired_leads,
            "inserted_events": inserted_events,
            "inserted_transcripts": inserted_transcripts,
            "quarantined_payloads": quarantined_payloads,
            "errors": errors[:50],
            "lookback_hours": lookback_hours,
            "unresolved_only": unresolved_only,
            "campaign_tag": campaign_tag or None,
        }
        self._emit("postcall_reconcile", report)
        return report

    def _fetch_call_sessions(self, *, cutoff: datetime, limit: int) -> List[Dict[str, Any]]:
        params = {
            "select": "id,lead_id,retell_call_id,agent_type,outcome,summary,duration,created_at",
            "retell_call_id": "not.is.null",
            "created_at": f"gte.{cutoff.isoformat()}",
            "order": "created_at.desc",
            "limit": str(limit),
        }
        resp = requests.get(
            f"{self.supabase_url}/rest/v1/call_sessions",
            headers=self._sb_headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _fetch_lead_map(self, lead_ids: Iterable[Any]) -> Dict[str, Dict[str, Any]]:
        ids = [str(item) for item in lead_ids if item]
        if not ids:
            return {}
        rows: List[Dict[str, Any]] = []
        for idx in range(0, len(ids), 120):
            batch = ids[idx : idx + 120]
            params = {
                "select": "id,place_id,source,business_name,phone,status,dm_email,last_contacted_at",
                "id": f"in.({','.join(batch)})",
            }
            resp = requests.get(
                f"{self.supabase_url}/rest/v1/leads",
                headers=self._sb_headers(),
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            rows.extend(resp.json())
        return {str(row.get("id")): row for row in rows if row.get("id")}

    def _get_retell_call(self, retell_call_id: str) -> Dict[str, Any]:
        resp = requests.get(
            f"{self.retell_base}/v2/get-call/{retell_call_id}",
            headers=self._retell_headers(),
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise RuntimeError("Retell response must be object")
        return data

    def _patch_call_session_if_needed(self, session: Dict[str, Any], record: Dict[str, Any], *, force: bool) -> bool:
        patch: Dict[str, Any] = {}
        if force or (not session.get("outcome") and record.get("outcome")):
            patch["outcome"] = record.get("outcome")
        if force or (not session.get("summary") and record.get("summary")):
            patch["summary"] = record.get("summary")
        if force or (not session.get("duration") and record.get("duration_ms")):
            patch["duration"] = max(1, int(round(float(record["duration_ms"]) / 1000.0)))
        if not patch:
            return False
        resp = requests.patch(
            f"{self.supabase_url}/rest/v1/call_sessions",
            headers=self._sb_headers(),
            params={"id": f"eq.{session['id']}"},
            data=json.dumps(patch),
            timeout=20,
        )
        resp.raise_for_status()
        return True

    def _patch_lead_and_segment_if_needed(self, lead: Dict[str, Any], record: Dict[str, Any], *, force: bool) -> bool:
        lead_id = str(lead.get("id") or record.get("lead_id") or "")
        outcome = str(record.get("outcome") or "")
        if not lead_id or not outcome:
            return False

        target_status = OUTCOME_STATUS_MAP.get(outcome, "NURTURE")
        patch: Dict[str, Any] = {
            "status": target_status,
            "last_contacted_at": datetime.now(timezone.utc).isoformat(),
            "positive_signal": outcome in {"GRANTED", "STALLED"},
            "decision_maker_confirmed": outcome == "GRANTED",
        }
        dm_email = record.get("dm_email")
        if dm_email:
            patch["dm_email"] = dm_email
        if not force:
            # If lead is already DNC, do not overwrite it downward.
            if str(lead.get("status") or "").upper() == "DNC" and target_status != "DNC":
                patch["status"] = "DNC"

        resp = requests.patch(
            f"{self.supabase_url}/rest/v1/leads",
            headers=self._sb_headers(),
            params={"id": f"eq.{lead_id}"},
            data=json.dumps(patch),
            timeout=20,
        )
        resp.raise_for_status()

        seg_headers = self._sb_headers()
        seg_headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        seg_resp = requests.post(
            f"{self.supabase_url}/rest/v1/segments",
            headers=seg_headers,
            params={"on_conflict": "lead_id"},
            data=json.dumps(
                {
                    "lead_id": lead_id,
                    "segment": outcome,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }
            ),
            timeout=20,
        )
        seg_resp.raise_for_status()
        return True

    def _upsert_postcall_event(self, session: Dict[str, Any], lead: Dict[str, Any], retell_payload: Dict[str, Any]) -> bool:
        lead_id = str(session.get("lead_id") or "")
        call_id = str(session.get("retell_call_id") or "")
        if not lead_id or not call_id:
            return False
        headers = self._sb_headers()
        headers["Prefer"] = "resolution=ignore-duplicates,return=representation"
        resp = requests.post(
            f"{self.supabase_url}/rest/v1/lead_events",
            headers=headers,
            params={"on_conflict": "idempotency_key"},
            data=json.dumps(
                {
                    "lead_id": lead_id,
                    "place_id": lead.get("place_id"),
                    "event_type": "retell_postcall",
                    "idempotency_key": f"{call_id}-postcall",
                    "payload_json": retell_payload,
                }
            ),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        return bool(data)

    def _persist_validation_failure(self, failure: Any) -> None:
        report_row, quarantine_row = build_persistence_records(failure)
        headers = self._sb_headers()
        for table, row in (
            ("shacl_validation_reports", report_row),
            ("ingest_quarantine", quarantine_row),
        ):
            resp = requests.post(
                f"{self.supabase_url}/rest/v1/{table}",
                headers=headers,
                data=json.dumps(row),
                timeout=20,
            )
            resp.raise_for_status()

    def _upsert_transcript_and_turns(self, record: Dict[str, Any], turns: List[Dict[str, Any]]) -> None:
        headers = self._sb_headers()
        write_headers = dict(headers)
        write_headers["Prefer"] = "return=representation,resolution=merge-duplicates"
        resp = requests.post(
            f"{self.supabase_url}/rest/v1/call_transcripts",
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
            return

        delete_resp = requests.delete(
            f"{self.supabase_url}/rest/v1/call_transcript_turns",
            headers=headers,
            params={"transcript_id": f"eq.{transcript_id}"},
            timeout=20,
        )
        delete_resp.raise_for_status()

        if not turns:
            return
        payload_rows: List[Dict[str, Any]] = []
        for turn in turns:
            payload_rows.append(
                {
                    "transcript_id": transcript_id,
                    "retell_call_id": record.get("retell_call_id"),
                    "turn_index": int(turn.get("turn_index", 0)),
                    "speaker": str(turn.get("speaker") or "unknown"),
                    "text": str(turn.get("text") or ""),
                    "start_ms": turn.get("start_ms"),
                    "end_ms": turn.get("end_ms"),
                    "confidence": turn.get("confidence"),
                    "payload_json": turn.get("payload_json") or {},
                }
            )
        for idx in range(0, len(payload_rows), 500):
            batch = payload_rows[idx : idx + 500]
            insert_resp = requests.post(
                f"{self.supabase_url}/rest/v1/call_transcript_turns",
                headers=headers,
                data=json.dumps(batch),
                timeout=30,
            )
            insert_resp.raise_for_status()

    def _transcript_tables_enabled(self) -> bool:
        if self._transcript_tables_available is not None:
            return self._transcript_tables_available
        try:
            t1 = requests.get(
                f"{self.supabase_url}/rest/v1/call_transcripts",
                headers=self._sb_headers(),
                params={"select": "id", "limit": "1"},
                timeout=10,
            )
            t2 = requests.get(
                f"{self.supabase_url}/rest/v1/call_transcript_turns",
                headers=self._sb_headers(),
                params={"select": "id", "limit": "1"},
                timeout=10,
            )
            self._transcript_tables_available = t1.status_code == 200 and t2.status_code == 200
        except requests.RequestException:
            self._transcript_tables_available = False
        return bool(self._transcript_tables_available)

    def _session_needs_repair(self, session: Dict[str, Any]) -> bool:
        return not session.get("outcome") or not session.get("summary") or not session.get("duration")

    def _sb_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }

    def _retell_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.retell_key}",
        }

    def _emit(self, event: str, payload: Dict[str, Any]) -> None:
        if self.telemetry:
            self.telemetry.emit(event, payload)
