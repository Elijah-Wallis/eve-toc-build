from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from ontology.client import OntologyClient


class OutboxPublisher:
    """
    Supabase-first outbox publisher.

    Delivery contract: effectively-once side effects per event_id idempotency key.
    """

    def __init__(self) -> None:
        self.ontology = OntologyClient()

    def fetch_unpublished(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.ontology.select(
            "canonical_outbox",
            {
                "select": "event_id,mutation_key,aggregate_type,aggregate_id,schema_version,entity_key,payload_delta,created_at,published_at",
                "published_at": "is.null",
                "order": "created_at.asc",
                "limit": str(max(1, int(limit))),
            },
        )

    def mark_published(self, event_id: str) -> None:
        patch = {"published_at": datetime.now(timezone.utc).isoformat()}
        self.ontology.patch(f"canonical_outbox?event_id=eq.{event_id}", patch)

    def record_consumer_apply(self, *, event_id: str, consumer_name: str) -> None:
        payload = {"event_id": event_id, "consumer_name": consumer_name}
        self.ontology.insert(
            "applied_events?on_conflict=event_id,consumer_name",
            payload,
            return_representation=True,
        )
