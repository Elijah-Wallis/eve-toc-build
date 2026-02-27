from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests


class OutboxPublisher:
    """
    Supabase-first outbox publisher.

    Delivery contract: effectively-once side effects per event_id idempotency key.
    """

    def __init__(self) -> None:
        self.supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self.supabase_url or not self.supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    def fetch_unpublished(self, limit: int = 100) -> List[Dict[str, Any]]:
        params = {
            "select": "event_id,mutation_key,aggregate_type,aggregate_id,schema_version,entity_key,payload_delta,created_at,published_at",
            "published_at": "is.null",
            "order": "created_at.asc",
            "limit": str(max(1, int(limit))),
        }
        resp = requests.get(
            f"{self.supabase_url}/rest/v1/canonical_outbox",
            headers=self._headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def mark_published(self, event_id: str) -> None:
        patch = {"published_at": datetime.now(timezone.utc).isoformat()}
        resp = requests.patch(
            f"{self.supabase_url}/rest/v1/canonical_outbox",
            headers=self._headers(),
            params={"event_id": f"eq.{event_id}"},
            data=json.dumps(patch),
            timeout=20,
        )
        resp.raise_for_status()

    def record_consumer_apply(self, *, event_id: str, consumer_name: str) -> None:
        headers = self._headers()
        headers["Prefer"] = "resolution=ignore-duplicates,return=representation"
        payload = {"event_id": event_id, "consumer_name": consumer_name}
        resp = requests.post(
            f"{self.supabase_url}/rest/v1/applied_events",
            headers=headers,
            params={"on_conflict": "event_id,consumer_name"},
            data=json.dumps(payload),
            timeout=20,
        )
        resp.raise_for_status()

    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
