from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ontology.client import OntologyClient


class ContextStore:
    """Persist long-context threads and events in Supabase."""

    def __init__(self, summarizer: Optional[Callable[[List[Dict[str, Any]]], str]] = None) -> None:
        self.ontology = OntologyClient()
        self.summarizer = summarizer or self._default_summarizer

    def create_thread(self, name: str, status: str = "active") -> Dict[str, Any]:
        record = {
            "name": name,
            "status": status,
            "last_summary": "",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return self._insert("context_threads", record, return_representation=True)

    def append_event(self, thread_id: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = {
            "thread_id": thread_id,
            "event_type": event_type,
            "payload_json": payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        event = self._insert("context_events", record, return_representation=True)
        self._touch_thread(thread_id)
        return event

    def get_thread_events(self, thread_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return self.ontology.select(
            "context_events",
            {
                "select": "event_type,payload_json,created_at",
                "thread_id": f"eq.{thread_id}",
                "order": "created_at.desc",
                "limit": str(limit),
            },
        )

    def summarize_thread(self, thread_id: str, limit: int = 50) -> str:
        events = list(reversed(self.get_thread_events(thread_id, limit=limit)))
        summary = self.summarizer(events)
        self._patch(
            f"context_threads?id=eq.{thread_id}",
            {"last_summary": summary, "updated_at": datetime.now(timezone.utc).isoformat()},
        )
        return summary

    def get_thread_context(self, thread_id: str, limit: int = 50) -> Dict[str, Any]:
        events = list(reversed(self.get_thread_events(thread_id, limit=limit)))
        summary = self.summarize_thread(thread_id, limit=limit)
        return {"thread_id": thread_id, "summary": summary, "events": events}

    def _touch_thread(self, thread_id: str) -> None:
        self._patch(
            f"context_threads?id=eq.{thread_id}",
            {"updated_at": datetime.now(timezone.utc).isoformat()},
        )

    def _default_summarizer(self, events: List[Dict[str, Any]]) -> str:
        chunks = []
        for event in events:
            payload = event.get("payload_json", {})
            chunks.append(f"{event.get('event_type')}: {payload}")
        return " | ".join(chunks)[-4000:]

    def _insert(self, table: str, record: Dict[str, Any], return_representation: bool = False) -> Dict[str, Any]:
        return self.ontology.insert(table, record, return_representation=return_representation)

    def _patch(self, table_query: str, patch: Dict[str, Any]) -> None:
        self.ontology.patch(table_query, patch)
