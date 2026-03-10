from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

from src.runtime.runtime_paths import state_path
from src.runtime.telemetry import Telemetry


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _in_filter(values: Iterable[str]) -> str:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return f"in.({','.join(cleaned)})" if cleaned else "in.()"


class OntologyClient:
    """Canonical boundary for ontology and runtime persistence.

    All production data access must route through this client so provenance and
    auditability are centralized even while legacy runtime tables still back the
    current operating model.
    """

    OBJECT_TABLES = {
        "PatientJourney": "leads",
        "ClinicalEncounter": "call_sessions",
        "AestheticProcedure/DentalService": "segments",
        "Provider": "",
        "ClinicLocation": "",
        "ConsumableInventory": "",
        "FinancialEvent": "lead_events",
        "ComplianceRecord": "stoplist",
    }

    def __init__(self, telemetry: Optional[Telemetry] = None, *, actor: str = "ontology-client") -> None:
        self.telemetry = telemetry
        self.actor = actor
        self.base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self.base_url or not self.service_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        self.audit_path = Path(state_path("ontology", "audit.jsonl"))
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def get_patient_journey(
        self,
        *,
        lead_id: str = "",
        phone: str = "",
        select: str = "id,source,place_id,business_name,phone,email,website,address,city,state,zip,status,lead_type,decision_maker_confirmed,positive_signal,touch_count,last_contacted_at,next_touch_at,rating,reviews_count,categories,created_at,paused_until,dm_email",
    ) -> Optional[Dict[str, Any]]:
        params: Dict[str, str] = {"select": select, "limit": "1"}
        if lead_id:
            params["id"] = f"eq.{lead_id}"
        elif phone:
            params["phone"] = f"eq.{phone}"
        else:
            raise RuntimeError("lead_id or phone is required")
        rows = self.list_patient_journeys(params, object_name="PatientJourney")
        return rows[0] if rows else None

    def list_patient_journeys(
        self,
        params: Dict[str, Any],
        *,
        object_name: str = "PatientJourney",
        provenance: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        rows = self._list("leads", params, object_name=object_name, provenance=provenance)
        return rows

    def list_patient_journeys_by_ids(self, lead_ids: Iterable[Any], *, select: str) -> List[Dict[str, Any]]:
        ids = [str(item) for item in lead_ids if item]
        if not ids:
            return []
        rows: List[Dict[str, Any]] = []
        for idx in range(0, len(ids), 120):
            batch = ids[idx : idx + 120]
            rows.extend(
                self.list_patient_journeys(
                    {"select": select, "id": _in_filter(batch)},
                    provenance=self._provenance("PatientJourney", ",".join(batch)),
                )
            )
        return rows

    def patch_patient_journey(self, lead_id: str, patch: Dict[str, Any], *, provenance: Optional[Dict[str, Any]] = None) -> None:
        self._patch(
            f"leads?id=eq.{lead_id}",
            patch,
            object_name="PatientJourney",
            provenance=provenance or self._provenance("PatientJourney", lead_id, payload=patch),
        )

    def patch_patient_journeys(self, filters: Dict[str, str], patch: Dict[str, Any], *, provenance: Optional[Dict[str, Any]] = None) -> None:
        params = "&".join(f"{key}={value}" for key, value in filters.items())
        self._patch(
            f"leads?{params}",
            patch,
            object_name="PatientJourney",
            provenance=provenance or self._provenance("PatientJourney", params or "filtered", payload=patch),
        )

    def upsert_patient_journeys(self, records: List[Dict[str, Any]], *, on_conflict: str = "place_id") -> List[Dict[str, Any]]:
        if not records:
            return []
        rows = self._insert(
            "leads",
            records,
            object_name="PatientJourney",
            provenance=self._provenance("PatientJourney", f"batch:{on_conflict}", payload=records),
            extra_headers={"Prefer": "resolution=merge-duplicates,return=representation"},
            params={"on_conflict": on_conflict},
            expect_list=True,
        )
        return rows if isinstance(rows, list) else [rows]

    def upsert_patient_journey_event(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        headers = {"Prefer": "resolution=ignore-duplicates,return=representation"}
        provenance = self._provenance(
            "FinancialEvent",
            str(record.get("idempotency_key") or record.get("lead_id") or "event"),
            evidence_uri=f"lead_events:{record.get('event_type') or 'unknown'}",
            payload=record,
        )
        return self._insert(
            "lead_events",
            record,
            object_name="FinancialEvent",
            provenance=provenance,
            extra_headers=headers,
            params={"on_conflict": "idempotency_key"},
            expect_list=True,
        )

    def list_recent_patient_journey_events(self, lead_id: str, limit: int = 25) -> List[Dict[str, Any]]:
        return self._list(
            "lead_events",
            {
                "select": "id,lead_id,event_type,idempotency_key,payload_json,created_at",
                "lead_id": f"eq.{lead_id}",
                "order": "created_at.desc",
                "limit": str(max(1, min(int(limit), 200))),
            },
            object_name="FinancialEvent",
            provenance=self._provenance("FinancialEvent", lead_id),
        )

    def upsert_patient_journey_segment(self, lead_id: str, segment: str, last_updated: str) -> None:
        headers = {"Prefer": "resolution=merge-duplicates,return=minimal"}
        payload = {"lead_id": lead_id, "segment": segment, "last_updated": last_updated}
        self._insert(
            "segments",
            payload,
            object_name="AestheticProcedure/DentalService",
            provenance=self._provenance("AestheticProcedure/DentalService", lead_id, payload=payload),
            extra_headers=headers,
            params={"on_conflict": "lead_id"},
        )

    def list_compliance_phones(self) -> List[str]:
        rows = self._list(
            "stoplist",
            {"select": "phone"},
            object_name="ComplianceRecord",
            provenance=self._provenance("ComplianceRecord", "stoplist"),
        )
        return [str(row.get("phone") or "") for row in rows if row.get("phone")]

    def upsert_compliance_record(self, record: Dict[str, Any]) -> None:
        self._unsupported("ComplianceRecord", detail=record)

    def get_clinical_encounter(self, encounter_id: str) -> Optional[Dict[str, Any]]:
        rows = self.list_clinical_encounters(
            {"select": "*", "id": f"eq.{encounter_id}", "limit": "1"},
            provenance=self._provenance("ClinicalEncounter", encounter_id),
        )
        return rows[0] if rows else None

    def list_clinical_encounters(
        self,
        params: Dict[str, Any],
        *,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return self._list(
            "call_sessions",
            params,
            object_name="ClinicalEncounter",
            provenance=provenance,
        )

    def patch_clinical_encounter(self, encounter_id: str, patch: Dict[str, Any]) -> None:
        self._patch(
            f"call_sessions?id=eq.{encounter_id}",
            patch,
            object_name="ClinicalEncounter",
            provenance=self._provenance("ClinicalEncounter", encounter_id, payload=patch),
        )

    def upsert_clinical_transcript(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        headers = {"Prefer": "return=representation,resolution=merge-duplicates"}
        rows = self._insert(
            "call_transcripts",
            record,
            object_name="ClinicalEncounter",
            provenance=self._provenance(
                "ClinicalEncounter",
                str(record.get("retell_call_id") or record.get("call_session_id") or "transcript"),
                evidence_uri=str(record.get("recording_url") or ""),
                payload=record,
            ),
            extra_headers=headers,
            params={"on_conflict": "retell_call_id"},
            expect_list=True,
        )
        if isinstance(rows, list):
            return rows[0] if rows else None
        return rows

    def replace_clinical_transcript_turns(
        self,
        transcript_id: str,
        retell_call_id: str,
        turns: List[Dict[str, Any]],
    ) -> None:
        self._delete(
            "call_transcript_turns",
            params={"transcript_id": f"eq.{transcript_id}"},
            object_name="ClinicalEncounter",
            provenance=self._provenance("ClinicalEncounter", transcript_id, evidence_uri=f"retell_call:{retell_call_id}"),
        )
        if not turns:
            return
        for idx in range(0, len(turns), 500):
            batch = turns[idx : idx + 500]
            self._insert(
                "call_transcript_turns",
                batch,
                object_name="ClinicalEncounter",
                provenance=self._provenance("ClinicalEncounter", transcript_id, evidence_uri=f"retell_call:{retell_call_id}", payload=batch),
                expect_list=False,
            )

    def transcript_tables_enabled(self) -> bool:
        try:
            self._list("call_transcripts", {"select": "id", "limit": "1"}, object_name="ClinicalEncounter")
            self._list("call_transcript_turns", {"select": "id", "limit": "1"}, object_name="ClinicalEncounter")
            return True
        except requests.RequestException:
            return False

    def list_clinical_transcripts(
        self,
        params: Dict[str, Any],
        *,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return self._list(
            "call_transcripts",
            params,
            object_name="ClinicalEncounter",
            provenance=provenance,
        )

    def list_clinical_transcript_turns(
        self,
        params: Dict[str, Any],
        *,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return self._list(
            "call_transcript_turns",
            params,
            object_name="ClinicalEncounter",
            provenance=provenance,
        )

    def persist_validation_failure(self, report_row: Dict[str, Any], quarantine_row: Dict[str, Any]) -> None:
        for table, row in (("shacl_validation_reports", report_row), ("ingest_quarantine", quarantine_row)):
            self._insert(
                table,
                row,
                object_name="ComplianceRecord",
                provenance=self._provenance("ComplianceRecord", str(row.get("event_id") or table), payload=row),
            )

    def get_provider(self, provider_identifier: str) -> None:
        self._unsupported("Provider", detail={"provider_identifier": provider_identifier})

    def upsert_provider(self, record: Dict[str, Any]) -> None:
        self._unsupported("Provider", detail=record)

    def get_clinic_location(self, location_identifier: str) -> None:
        self._unsupported("ClinicLocation", detail={"location_identifier": location_identifier})

    def upsert_clinic_location(self, record: Dict[str, Any]) -> None:
        self._unsupported("ClinicLocation", detail=record)

    def upsert_consumable_inventory(self, record: Dict[str, Any]) -> None:
        self._unsupported("ConsumableInventory", detail=record)

    def get_financial_event(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        rows = self._list(
            "lead_events",
            {"select": "*", "idempotency_key": f"eq.{transaction_id}", "limit": "1"},
            object_name="FinancialEvent",
            provenance=self._provenance("FinancialEvent", transaction_id),
        )
        return rows[0] if rows else None

    def create_runtime_task(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return self._insert(
            "tasks",
            record,
            object_name="PatientJourney",
            provenance=self._provenance("PatientJourney", str(record.get("type") or "task"), payload=record),
            extra_headers={"Prefer": "return=representation"},
        )

    def list_ready_runtime_tasks(self, limit: int) -> List[Dict[str, Any]]:
        now = _utcnow_iso()
        params = {
            "select": "id,type,payload_json,retries,max_retries,scheduled_for",
            "status": "eq.queued",
            "scheduled_for": f"lte.{now}",
            "order": "scheduled_for.asc",
            "limit": str(limit),
        }
        return self._list("tasks", params, object_name="PatientJourney", provenance=self._provenance("PatientJourney", "runtime-tasks"))

    def lock_runtime_task(self, task_id: str, host_id: str) -> List[Dict[str, Any]]:
        patch = {"status": "running", "locked_by": host_id, "locked_at": _utcnow_iso()}
        return self._patch(
            f"tasks?id=eq.{task_id}&status=eq.queued",
            patch,
            object_name="PatientJourney",
            provenance=self._provenance("PatientJourney", task_id, payload=patch),
            return_representation=True,
        )

    def patch_runtime_task(self, task_id: str, patch: Dict[str, Any]) -> None:
        self._patch(
            f"tasks?id=eq.{task_id}",
            patch,
            object_name="PatientJourney",
            provenance=self._provenance("PatientJourney", task_id, payload=patch),
        )

    def patch_runtime_task_query(self, query: str, patch: Dict[str, Any], *, return_representation: bool = False) -> List[Dict[str, Any]]:
        return self._patch(
            f"tasks?{query}",
            patch,
            object_name="PatientJourney",
            provenance=self._provenance("PatientJourney", query, payload=patch),
            return_representation=return_representation,
        )

    def find_runtime_tasks_by_idempotency_key(self, key: str) -> List[Dict[str, Any]]:
        return self._list(
            "tasks",
            {
                "select": "id",
                "payload_json->>idempotency_key": f"eq.{key}",
                "status": "in.(running,completed)",
            },
            object_name="PatientJourney",
            provenance=self._provenance("PatientJourney", key),
        )

    def create_runtime_task_run(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return self._insert(
            "task_runs",
            record,
            object_name="ClinicalEncounter",
            provenance=self._provenance("ClinicalEncounter", str(record.get("task_id") or "task-run"), payload=record),
        )

    def list_runtime_task_runs(self, limit: int = 5) -> List[Dict[str, Any]]:
        return self._list(
            "task_runs",
            {"select": "id,task_id,status,started_at,ended_at,error", "order": "created_at.desc", "limit": str(limit)},
            object_name="ClinicalEncounter",
            provenance=self._provenance("ClinicalEncounter", "task-runs"),
        )

    def create_context_thread(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return self._insert(
            "context_threads",
            record,
            object_name="PatientJourney",
            provenance=self._provenance("PatientJourney", str(record.get("name") or "context-thread"), payload=record),
            extra_headers={"Prefer": "return=representation"},
        )

    def append_context_event(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return self._insert(
            "context_events",
            record,
            object_name="ClinicalEncounter",
            provenance=self._provenance("ClinicalEncounter", str(record.get("thread_id") or "context-event"), payload=record),
            extra_headers={"Prefer": "return=representation"},
        )

    def list_context_events(self, thread_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return self._list(
            "context_events",
            {
                "select": "event_type,payload_json,created_at",
                "thread_id": f"eq.{thread_id}",
                "order": "created_at.desc",
                "limit": str(limit),
            },
            object_name="ClinicalEncounter",
            provenance=self._provenance("ClinicalEncounter", thread_id),
        )

    def update_context_thread(self, thread_id: str, patch: Dict[str, Any]) -> None:
        self._patch(
            f"context_threads?id=eq.{thread_id}",
            patch,
            object_name="PatientJourney",
            provenance=self._provenance("PatientJourney", thread_id, payload=patch),
        )

    def list_runtime_cron_jobs(self) -> List[Dict[str, Any]]:
        return self._list(
            "cron_jobs",
            {
                "select": "id,name,cron,task_type,payload_json,last_run_at,next_run_at,active",
                "active": "eq.true",
            },
            object_name="ComplianceRecord",
            provenance=self._provenance("ComplianceRecord", "cron-jobs"),
        )

    def patch_runtime_cron_job(self, job_id: str, patch: Dict[str, Any]) -> None:
        self._patch(
            f"cron_jobs?id=eq.{job_id}",
            patch,
            object_name="ComplianceRecord",
            provenance=self._provenance("ComplianceRecord", job_id, payload=patch),
        )

    def upsert_runtime_cron_job(self, record: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Prefer": "return=representation,resolution=merge-duplicates"}
        try:
            rows = self._insert(
                "cron_jobs",
                record,
                object_name="ComplianceRecord",
                provenance=self._provenance("ComplianceRecord", str(record.get("name") or "cron-job"), payload=record),
                extra_headers=headers,
                params={"on_conflict": "name"},
                expect_list=True,
            )
            return rows[0] if isinstance(rows, list) and rows else rows
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 409:
                raise
            rows = self._patch(
                f"cron_jobs?name=eq.{record['name']}",
                {
                    "cron": record.get("cron"),
                    "task_type": record.get("task_type"),
                    "payload_json": record.get("payload_json"),
                    "active": record.get("active", True),
                    "updated_at": record.get("updated_at", _utcnow_iso()),
                },
                object_name="ComplianceRecord",
                provenance=self._provenance("ComplianceRecord", str(record.get("name") or "cron-job"), payload=record),
                return_representation=True,
            )
            return rows[0] if rows else {}

    def runtime_tasks_health(self) -> Dict[str, Any]:
        try:
            response = self._request(
                "get",
                f"{self.base_url}/rest/v1/tasks",
                headers=self._headers(),
                params={"select": "id", "limit": "1"},
                timeout=15,
            )
            return {"status": "ok" if response.status_code == 200 else "error", "code": response.status_code}
        except requests.RequestException as exc:
            return {"status": "error", "error": f"{type(exc).__name__}:{exc}"}

    def daily_operations_summary(self, day: date) -> Dict[str, Any]:
        today = day.isoformat()
        leads = self.list_patient_journeys({"select": "id,created_at", "created_at": f"gte.{today}"})
        encounters = self.list_clinical_encounters(
            {"select": "id,created_at", "created_at": f"gte.{today}"},
            provenance=self._provenance("ClinicalEncounter", today),
        )
        segments = self._list(
            "segments",
            {"select": "segment,last_updated", "last_updated": f"gte.{today}"},
            object_name="AestheticProcedure/DentalService",
            provenance=self._provenance("AestheticProcedure/DentalService", today),
        )
        return {
            "date": today,
            "leads": len(leads),
            "call_sessions": len(encounters),
            "segments": len(segments),
        }

    def fetch_unpublished_outbox_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._list(
            "canonical_outbox",
            {
                "select": "event_id,mutation_key,aggregate_type,aggregate_id,schema_version,entity_key,payload_delta,created_at,published_at",
                "published_at": "is.null",
                "order": "created_at.asc",
                "limit": str(max(1, int(limit))),
            },
            object_name="FinancialEvent",
            provenance=self._provenance("FinancialEvent", "canonical-outbox"),
        )

    def mark_outbox_event_published(self, event_id: str) -> None:
        self._patch(
            f"canonical_outbox?event_id=eq.{event_id}",
            {"published_at": _utcnow_iso()},
            object_name="FinancialEvent",
            provenance=self._provenance("FinancialEvent", event_id),
        )

    def record_outbox_consumer_apply(self, event_id: str, consumer_name: str) -> None:
        headers = {"Prefer": "resolution=ignore-duplicates,return=representation"}
        payload = {"event_id": event_id, "consumer_name": consumer_name}
        self._insert(
            "applied_events",
            payload,
            object_name="ComplianceRecord",
            provenance=self._provenance("ComplianceRecord", f"{event_id}:{consumer_name}", payload=payload),
            extra_headers=headers,
            params={"on_conflict": "event_id,consumer_name"},
        )

    def upsert_outbox_event(self, record: Dict[str, Any]) -> None:
        headers = {"Prefer": "resolution=merge-duplicates,return=minimal"}
        self._insert(
            "canonical_outbox",
            record,
            object_name="FinancialEvent",
            provenance=self._provenance("FinancialEvent", str(record.get("event_id") or "outbox-event"), payload=record),
            extra_headers=headers,
            params={"on_conflict": "event_id"},
        )

    def query_object(
        self,
        *,
        object_name: str,
        filters: Optional[Dict[str, Any]] = None,
        select: str = "*",
        limit: int = 25,
        order: str = "",
    ) -> List[Dict[str, Any]]:
        table = self.OBJECT_TABLES.get(object_name, "")
        if not table:
            self._unsupported(object_name, detail={"filters": filters or {}})
        params: Dict[str, Any] = {"select": select, "limit": str(max(1, int(limit)))}
        for key, value in (filters or {}).items():
            params[key] = value
        if order:
            params["order"] = order
        return self._list(
            table,
            params,
            object_name=object_name,
            provenance=self._provenance(object_name, json.dumps(filters or {}, sort_keys=True)),
        )

    def _unsupported(self, object_name: str, *, detail: Dict[str, Any]) -> None:
        raise RuntimeError(f"{object_name} is not yet backed by the current runtime schema: {detail}")

    def _list(
        self,
        table: str,
        params: Dict[str, Any],
        *,
        object_name: str,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        response = self._request(
            "get",
            f"{self.base_url}/rest/v1/{table}",
            headers=self._headers(),
            params=params,
        )
        response.raise_for_status()
        self._audit("read", object_name, table, provenance or self._provenance(object_name, table), {"params": params})
        data = response.json()
        return data if isinstance(data, list) else [data]

    def _insert(
        self,
        table: str,
        record: Any,
        *,
        object_name: str,
        provenance: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        expect_list: bool = False,
    ) -> Any:
        headers = self._headers()
        headers.update(extra_headers or {})
        response = self._request(
            "post",
            f"{self.base_url}/rest/v1/{table}",
            headers=headers,
            params=params,
            data=json.dumps(record),
        )
        response.raise_for_status()
        self._audit("write", object_name, table, provenance, {"params": params or {}, "record_type": type(record).__name__})
        try:
            data = response.json()
        except ValueError:
            return [] if expect_list else {}
        if expect_list:
            return data
        return data[0] if isinstance(data, list) and data else data

    def _patch(
        self,
        table_query: str,
        patch: Dict[str, Any],
        *,
        object_name: str,
        provenance: Dict[str, Any],
        return_representation: bool = False,
    ) -> List[Dict[str, Any]]:
        headers = self._headers()
        if return_representation:
            headers["Prefer"] = "return=representation"
        response = self._request(
            "patch",
            f"{self.base_url}/rest/v1/{table_query}",
            headers=headers,
            data=json.dumps(patch),
        )
        response.raise_for_status()
        self._audit("write", object_name, table_query, provenance, {"patch_keys": sorted(patch.keys())})
        if not return_representation:
            return []
        data = response.json()
        return data if isinstance(data, list) else [data]

    def _delete(
        self,
        table: str,
        *,
        params: Dict[str, Any],
        object_name: str,
        provenance: Dict[str, Any],
    ) -> None:
        response = self._request(
            "delete",
            f"{self.base_url}/rest/v1/{table}",
            headers=self._headers(),
            params=params,
        )
        response.raise_for_status()
        self._audit("delete", object_name, table, provenance, {"params": params})

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        timeout = kwargs.pop("timeout", 30)
        return requests.request(method, url, timeout=timeout, **kwargs)

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
        }

    def _provenance(
        self,
        object_name: str,
        source_record_id: str,
        *,
        evidence_uri: str = "",
        payload: Any = None,
    ) -> Dict[str, Any]:
        ingested_at = _utcnow_iso()
        payload_blob = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str) if payload is not None else ""
        lineage_hash = sha256(f"{object_name}:{source_record_id}:{payload_blob}".encode("utf-8")).hexdigest()
        return {
            "source_system": "supabase-runtime",
            "source_record_id": str(source_record_id or object_name),
            "observed_at": ingested_at,
            "ingested_at": ingested_at,
            "recorded_by": self.actor,
            "evidence_uri": evidence_uri or f"table:{self.OBJECT_TABLES.get(object_name, object_name)}",
            "lineage_hash": lineage_hash,
        }

    def _audit(
        self,
        action: str,
        object_name: str,
        target: str,
        provenance: Dict[str, Any],
        detail: Dict[str, Any],
    ) -> None:
        record = {
            "ts": _utcnow_iso(),
            "actor": self.actor,
            "action": action,
            "object_name": object_name,
            "target": target,
            "provenance": provenance,
            "detail": detail,
        }
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        if self.telemetry:
            self.telemetry.emit("ontology_client", {"action": action, "object_name": object_name, "target": target})
