from __future__ import annotations

from typing import Any, Dict, List

from ontology.client import OntologyClient


class OutboxPublisher:
    """
    Supabase-first outbox publisher.

    Delivery contract: effectively-once side effects per event_id idempotency key.
    """

    def __init__(self) -> None:
        self.ontology = OntologyClient(actor="outbox-publisher")

    def fetch_unpublished(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.ontology.fetch_unpublished_outbox_events(limit)

    def mark_published(self, event_id: str) -> None:
        self.ontology.mark_outbox_event_published(event_id)

    def record_consumer_apply(self, *, event_id: str, consumer_name: str) -> None:
        self.ontology.record_outbox_consumer_apply(event_id=event_id, consumer_name=consumer_name)
