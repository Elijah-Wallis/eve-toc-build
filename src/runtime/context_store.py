from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ontology.client import OntologyClient


class ContextStore:
    """Persist long-context threads and events through the ontology boundary."""

    def __init__(self, summarizer: Optional[Callable[[List[Dict[str, Any]]], str]] = None) -> None:
        self.ontology = OntologyClient(actor="context-store")
        self.summarizer = summarizer or self._default_summarizer

    def create_thread(self, name: str, status: str = "active") -> Dict[str, Any]:
        record = {
            "name": name,
            "status": status,
            "last_summary": "",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return self.ontology.create_context_thread(record)

    def append_event(self, thread_id: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = {
            "thread_id": thread_id,
            "event_type": event_type,
            "payload_json": payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        event = self.ontology.append_context_event(record)
        self._touch_thread(thread_id)
        return event

    def get_thread_events(self, thread_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return self.ontology.list_context_events(thread_id, limit)

    def summarize_thread(self, thread_id: str, limit: int = 50) -> str:
        events = list(reversed(self.get_thread_events(thread_id, limit=limit)))
        summary = self.summarizer(events)
        self.ontology.update_context_thread(
            thread_id,
            {"last_summary": summary, "updated_at": datetime.now(timezone.utc).isoformat()},
        )
        return summary

    def get_thread_context(self, thread_id: str, limit: int = 50) -> Dict[str, Any]:
        events = list(reversed(self.get_thread_events(thread_id, limit=limit)))
        summary = self.summarize_thread(thread_id, limit=limit)
        return {"thread_id": thread_id, "summary": summary, "events": events}

    def _touch_thread(self, thread_id: str) -> None:
        self.ontology.update_context_thread(thread_id, {"updated_at": datetime.now(timezone.utc).isoformat()})

    def _default_summarizer(self, events: List[Dict[str, Any]]) -> str:
        chunks = []
        for event in events:
            payload = event.get("payload_json", {})
            chunks.append(f"{event.get('event_type')}: {payload}")
        return " | ".join(chunks)[-4000:]
