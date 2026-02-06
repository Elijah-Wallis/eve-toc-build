from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import requests


class ContextStore:
    """Persist long-context threads and events in Supabase."""

    def __init__(self, summarizer: Optional[Callable[[List[Dict[str, Any]]], str]] = None) -> None:
        self.supabase_url = os.environ.get("SUPABASE_URL", "")
        self.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self.supabase_url or not self.supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
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
        url = (
            f"{self.supabase_url}/rest/v1/context_events?"
            f"select=event_type,payload_json,created_at&"
            f"thread_id=eq.{thread_id}&order=created_at.desc&limit={limit}"
        )
        return self._get(url)

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

    def _get(self, url: str) -> List[Dict[str, Any]]:
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _insert(self, table: str, record: Dict[str, Any], return_representation: bool = False) -> Dict[str, Any]:
        headers = self._headers()
        if return_representation:
            headers["Prefer"] = "return=representation"
        resp = requests.post(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=headers,
            data=json.dumps(record),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data[0] if isinstance(data, list) and data else data

    def _patch(self, table_query: str, patch: Dict[str, Any]) -> None:
        resp = requests.patch(
            f"{self.supabase_url}/rest/v1/{table_query}",
            headers=self._headers(),
            data=json.dumps(patch),
            timeout=30,
        )
        resp.raise_for_status()

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }
