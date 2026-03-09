"""
Eve L5 Agent Base
=================
Shared base class for all 15 L5 hive-mind agents.
Provides: Supabase integration, heartbeat loop, outbox messaging,
ontology node management, derivative intelligence pipeline, and
structured Pydantic output enforcement.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger("eve.l5")


# ---------------------------------------------------------------------------
# Pydantic output models (standardised across all agents)
# ---------------------------------------------------------------------------

class ConfidenceInterval(BaseModel):
    lower: float
    upper: float
    confidence: float = 0.95


class ActionOutput(BaseModel):
    action: str
    projected_roi: float
    roi_ci: ConfidenceInterval
    validation_plan: str
    kill_criteria: str
    agent_id: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OntologyNode(BaseModel):
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    causal_relations: List[Dict[str, Any]] = Field(default_factory=list)
    quantitative_thresholds: Dict[str, float] = Field(default_factory=dict)
    statistical_confidence: float = 0.0
    self_correction_triggers: List[str] = Field(default_factory=list)
    derivative_intelligence_hooks: List[str] = Field(default_factory=list)
    roi_projection_link: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OutboxMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_agent: str
    target_agent: str = "*"
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    consumed: bool = False


class HeartbeatRecord(BaseModel):
    agent_id: str
    tick: int = 0
    status: str = "alive"
    anomalies_detected: int = 0
    actions_emitted: int = 0
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Supabase thin wrapper (env-driven, no secrets in code)
# ---------------------------------------------------------------------------

class SupabaseClient:
    """Lazy-init Supabase client reading SUPABASE_URL and SUPABASE_KEY from env."""

    _instance: ClassVar[Optional[Any]] = None

    @classmethod
    def get(cls) -> Any:
        if cls._instance is not None:
            return cls._instance
        try:
            from supabase import create_client
        except ImportError as exc:
            raise RuntimeError("supabase package required: pip install supabase") from exc
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            logger.warning("SUPABASE_URL / SUPABASE_KEY not set — running in dry-run mode")
            return None
        cls._instance = create_client(url, key)
        return cls._instance


# ---------------------------------------------------------------------------
# Base Agent
# ---------------------------------------------------------------------------

class L5AgentBase(ABC):
    """Abstract base for every Eve L5 agent.

    Subclasses MUST implement:
        - ``role_id``         (class var)
        - ``display_name``    (class var)
        - ``cadence_seconds`` (class var, heartbeat interval)
        - ``poll_tables``     (class var, list of Supabase tables to watch)
        - ``vanity_metrics``  (class var)
        - ``signal_metrics``  (class var)
        - ``detect_anomalies``
        - ``derive_intelligence``
        - ``emit_actions``
    """

    role_id: ClassVar[str]
    display_name: ClassVar[str]
    cadence_seconds: ClassVar[int] = 60
    poll_tables: ClassVar[List[str]] = []
    vanity_metrics: ClassVar[List[str]] = []
    signal_metrics: ClassVar[List[str]] = []

    def __init__(self) -> None:
        self._tick = 0
        self._running = False
        self._sb = SupabaseClient.get()

    # -- Supabase helpers ---------------------------------------------------

    def sb_query(self, table: str, select: str = "*", filters: Optional[Dict] = None, limit: int = 100) -> List[Dict]:
        if self._sb is None:
            return []
        try:
            q = self._sb.table(table).select(select)
            for k, v in (filters or {}).items():
                q = q.eq(k, v)
            return q.limit(limit).execute().data or []
        except Exception:
            logger.exception("sb_query failed on %s", table)
            return []

    def sb_upsert(self, table: str, rows: List[Dict]) -> None:
        if self._sb is None or not rows:
            return
        try:
            self._sb.table(table).upsert(rows).execute()
        except Exception:
            logger.exception("sb_upsert failed on %s", table)

    def sb_insert(self, table: str, rows: List[Dict]) -> None:
        if self._sb is None or not rows:
            return
        try:
            self._sb.table(table).insert(rows).execute()
        except Exception:
            logger.exception("sb_insert failed on %s", table)

    # -- Outbox (hive-mind pub/sub) -----------------------------------------

    def publish(self, event_type: str, payload: Dict, target: str = "*") -> None:
        msg = OutboxMessage(
            source_agent=self.role_id,
            target_agent=target,
            event_type=event_type,
            payload=payload,
        )
        self.sb_insert("outbox", [msg.model_dump()])

    def consume_messages(self) -> List[Dict]:
        rows = self.sb_query(
            "outbox",
            filters={"consumed": False},
        )
        relevant = [r for r in rows if r.get("target_agent") in ("*", self.role_id)]
        ids = [r["message_id"] for r in relevant if "message_id" in r]
        if ids and self._sb is not None:
            try:
                for mid in ids:
                    self._sb.table("outbox").update({"consumed": True}).eq("message_id", mid).execute()
            except Exception:
                logger.exception("consume_messages: mark-consumed failed")
        return relevant

    # -- Ontology node management -------------------------------------------

    def upsert_ontology_node(self, node: OntologyNode) -> None:
        self.sb_upsert("ontology_nodes", [node.model_dump()])

    def query_ontology_nodes(self, entity: Optional[str] = None) -> List[Dict]:
        filters = {"entity": entity} if entity else None
        return self.sb_query("ontology_nodes", filters=filters)

    # -- Task creation ------------------------------------------------------

    def create_task(self, title: str, description: str, priority: int = 3, assigned_to: str = "") -> None:
        task = {
            "task_id": str(uuid.uuid4()),
            "title": title,
            "description": description,
            "priority": priority,
            "status": "pending",
            "created_by": self.role_id,
            "assigned_to": assigned_to or self.role_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.sb_insert("tasks", [task])

    # -- Heartbeat bookkeeping ----------------------------------------------

    def _record_heartbeat(self, anomalies: int, actions: int) -> None:
        rec = HeartbeatRecord(
            agent_id=self.role_id,
            tick=self._tick,
            anomalies_detected=anomalies,
            actions_emitted=actions,
        )
        self.sb_insert("heartbeats", [rec.model_dump()])

    # -- Data cleaning & linking (subclass may override) --------------------

    def clean_and_link(self, raw_rows: List[Dict]) -> List[Dict]:
        """Strip vanity fields, enrich with causal relation stubs."""
        vanity_lower = {v.lower() for v in self.vanity_metrics}
        cleaned: List[Dict] = []
        for row in raw_rows:
            out = {k: v for k, v in row.items() if k.lower() not in vanity_lower}
            out.setdefault("_linked_agent", self.role_id)
            out.setdefault("_cleaned_at", datetime.now(timezone.utc).isoformat())
            cleaned.append(out)
        return cleaned

    # -- Abstract pipeline stages -------------------------------------------

    @abstractmethod
    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        """Return list of anomaly dicts detected from polled data."""

    @abstractmethod
    def derive_intelligence(self, anomalies: List[Dict], data: Dict[str, List[Dict]]) -> List[ActionOutput]:
        """First-principles causal inference → sandbox sim → ROI projection."""

    @abstractmethod
    def emit_actions(self, actions: List[ActionOutput]) -> None:
        """Execute or publish derived actions."""

    # -- Single heartbeat tick ----------------------------------------------

    def tick(self) -> None:
        self._tick += 1
        logger.info("[%s] heartbeat tick=%d", self.role_id, self._tick)

        data: Dict[str, List[Dict]] = {}
        for tbl in self.poll_tables:
            raw = self.sb_query(tbl, limit=500)
            data[tbl] = self.clean_and_link(raw)

        messages = self.consume_messages()
        if messages:
            data["_inbox"] = messages

        anomalies = self.detect_anomalies(data)
        actions = self.derive_intelligence(anomalies, data)

        for act in actions:
            act.agent_id = self.role_id

        self.emit_actions(actions)
        self._record_heartbeat(len(anomalies), len(actions))

    # -- Continuous loop ----------------------------------------------------

    async def run_loop(self) -> None:
        self._running = True
        logger.info("[%s] starting heartbeat loop (cadence=%ds)", self.role_id, self.cadence_seconds)
        while self._running:
            try:
                self.tick()
            except Exception:
                logger.exception("[%s] tick failed", self.role_id)
            await asyncio.sleep(self.cadence_seconds)

    def stop(self) -> None:
        self._running = False
