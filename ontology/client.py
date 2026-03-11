from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import requests


class OntologyClient:
    """SSOT boundary for all Supabase access.

    This client centralizes data-plane access so runtime code does not perform raw
    Supabase REST calls directly. It also stamps provenance metadata for write paths.
    """

    def __init__(self) -> None:
        self.base = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self.base or not self.key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    def headers(self, *, json_body: bool = True, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        out = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        }
        if json_body:
            out["Content-Type"] = "application/json"
        if extra:
            out.update(extra)
        return out

    def select(self, table: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        resp = requests.get(
            f"{self.base}/rest/v1/{table}",
            headers=self.headers(json_body=False),
            params=params or {},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def insert(self, table: str, record: Dict[str, Any], *, return_representation: bool = False) -> Dict[str, Any]:
        payload = self._with_provenance(record)
        headers = self.headers()
        if return_representation:
            headers["Prefer"] = "return=representation"
        resp = requests.post(
            f"{self.base}/rest/v1/{table}",
            headers=headers,
            data=json.dumps(payload),
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        if isinstance(body, list):
            return body[0] if body else {}
        return body

    def patch(self, table_query: str, patch: Dict[str, Any], *, return_representation: bool = False) -> List[Dict[str, Any]]:
        headers = self.headers()
        if return_representation:
            headers["Prefer"] = "return=representation"
        resp = requests.patch(
            f"{self.base}/rest/v1/{table_query}",
            headers=headers,
            data=json.dumps(self._with_provenance(patch, write=False)),
            timeout=30,
        )
        resp.raise_for_status()
        if not resp.text:
            return []
        body = resp.json()
        return body if isinstance(body, list) else []

    def delete(self, table_query: str) -> None:
        resp = requests.delete(
            f"{self.base}/rest/v1/{table_query}",
            headers=self.headers(json_body=False),
            timeout=30,
        )
        resp.raise_for_status()

    def request(
        self,
        method: str,
        path: str,
        *,
        query: str = "",
        params: Optional[Dict[str, Any]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        url = f"{self.base}{path}{query}"
        resp = requests.request(
            method.upper(),
            url,
            headers=self.headers(extra=headers),
            params=params,
            json=self._with_provenance(json_payload or {}, write=method.upper() in {"POST", "PATCH", "PUT"})
            if json_payload is not None
            else None,
            timeout=timeout,
        )
        resp.raise_for_status()
        try:
            return {"data": resp.json(), "status_code": resp.status_code}
        except ValueError:
            return {"text": resp.text, "status_code": resp.status_code}

    # typed ontology-facing helpers
    def get_patient_journey(self, patient_id: str) -> Optional[Dict[str, Any]]:
        rows = self.select("leads", {"select": "*", "id": f"eq.{patient_id}", "limit": "1"})
        return rows[0] if rows else None

    def upsert_consumable_inventory(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert("lead_events", payload, return_representation=True)

    def record_compliance_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert("lead_events", payload, return_representation=True)

    def list_recent_financial_events(self, *, limit: int = 25) -> List[Dict[str, Any]]:
        return self.select("lead_events", {"select": "*", "order": "created_at.desc", "limit": str(limit)})

    def _with_provenance(self, payload: Dict[str, Any], *, write: bool = True) -> Dict[str, Any]:
        if not write:
            return dict(payload)
        out = dict(payload)
        out.setdefault("ontology_provenance", {})
        prov = dict(out.get("ontology_provenance") or {})
        prov.setdefault("source_system", "eve-runtime")
        prov.setdefault("source_record_ref", prov.get("source_record_ref") or "runtime")
        prov.setdefault("ingested_at", datetime.now(timezone.utc).isoformat())
        prov.setdefault("ingested_by", "ontology.client")
        out["ontology_provenance"] = prov
        return out
