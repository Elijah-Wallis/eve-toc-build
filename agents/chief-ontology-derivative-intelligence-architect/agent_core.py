from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from src.runtime.outbox import build_outbox_envelope  # noqa: E402
from src.runtime.runtime_paths import state_path  # noqa: E402
from src.runtime.telemetry import Telemetry  # noqa: E402


AGENT_SLUG = "chief-ontology-derivative-intelligence-architect"
AGENT_TITLE = "Chief Ontology & Derivative Intelligence Architect for Eve L5"
LIVE_GRAPHS = [
    "Patient Journey",
    "Revenue Cycle",
    "Clinical Protocols (DAGs)",
    "Capacity & Utilization",
    "Regulatory & Geo Constraints",
]
SIGNAL_METRICS = [
    "Free Cash Flow (FCF)",
    "Rev/Employee",
    "LTV:CAC payback (<6 months)",
    "Contribution Margin",
    "Chair/Operator Utilization (>92%)",
    "Conversion Velocity",
    "Referral Rate",
    "Resource Exchange",
    "Conflict Resolution Speed",
    "Ontology loop cycle time",
    "Action success rate (>=98%)",
    "Self-correction hit rate",
    "Causal prediction error (<2%)",
    "Scaling multiplier",
]
VANITY_METRICS = {
    "gross revenue",
    "headcount",
    "ebitda (adj)",
    "market share",
    "r&d spend",
    "followers",
    "likes",
    "brand awareness",
    "verbal commitments",
    "networking",
    "body weight",
    'subjective "feeling"',
    "aesthetic symmetry (non-functional)",
    "static taxonomies",
    "philosophical models",
    "diagram beauty",
    "node count",
}


class CausalRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    weight: float = Field(..., ge=-1.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    lag_seconds: int = Field(0, ge=0)
    evidence: str = "runtime"


class StandardizedNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity: str
    attributes: Dict[str, Any]
    causal_relations: List[CausalRelation]
    quantitative_thresholds: Dict[str, Any]
    statistical_confidence: float = Field(..., ge=0.0, le=1.0)
    self_correction_triggers: List[str]
    derivative_intelligence_hooks: Dict[str, Any]
    direct_ROI_projection_link_to_primary_signal_metrics: List[str]
    confidence: float = Field(..., ge=0.0, le=1.0)
    live_graph: str
    roi_hook: str


class ActionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    live_graph: str
    priority: str
    payload: Dict[str, Any]


class ROIProjection95CI(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lower: float
    expected: float
    upper: float
    unit: str
    primary_signal: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class ValidationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    target: str
    window: str
    owner: str = AGENT_SLUG


class KillCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    threshold: str
    reason: str


class StrictAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ActionSpec
    projected_ROI_95_CI: ROIProjection95CI
    validation_plan: List[ValidationCheck]
    kill_criteria: List[KillCriterion]


CausalRelation.model_rebuild()
StandardizedNode.model_rebuild()
ActionSpec.model_rebuild()
ROIProjection95CI.model_rebuild()
ValidationCheck.model_rebuild()
KillCriterion.model_rebuild()
StrictAgentOutput.model_rebuild()


class ChiefOntologyDerivativeIntelligenceArchitectAgent:
    """Background worker that keeps ontology signals executable and economically useful."""

    def __init__(
        self,
        *,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        session: Optional[requests.Session] = None,
        telemetry: Optional[Telemetry] = None,
    ) -> None:
        self.supabase_url = (supabase_url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.session = session or requests.Session()
        self.telemetry = telemetry or Telemetry(str(state_path("runtime", "telemetry.jsonl")))
        self.ontology_table = os.environ.get("EVE_ONTOLOGY_TABLE", "ontology_nodes")
        self.tasks_table = os.environ.get("EVE_TASKS_TABLE", "tasks")
        self.heartbeats_table = os.environ.get("EVE_HEARTBEATS_TABLE", "heartbeats")
        self.outbox_table = os.environ.get("EVE_OUTBOX_TABLE", "canonical_outbox")
        self.heartbeat_interval_seconds = min(
            900,
            max(60, int(os.environ.get("OPENCLAW_ONTOLOGY_HEARTBEAT_SECONDS", "300"))),
        )
        self.integration_latency_max_seconds = 60
        self.loop_velocity_max_hours = 24.0
        self.action_success_rate_min = 0.98
        self.causal_prediction_error_max = 0.02
        self.human_input_budget_ratio_max = 0.05

    def heartbeat(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.run_once(payload or {})

    def run_once(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._require_supabase()
        request_payload = dict(payload or {})
        snapshot = self._poll_supabase(limit=int(request_payload.get("limit", 50)))
        cleaned = self._clean_and_link(snapshot)
        anomaly = self._select_highest_leverage_anomaly(cleaned)
        decision = self._build_decision(anomaly, cleaned)
        self._upsert_candidate_nodes(cleaned["candidate_nodes"])
        event_id = self._publish_outbox_signal(decision, anomaly)
        self._record_heartbeat(decision, anomaly, event_id=event_id)
        if decision.action.priority == "p0" and request_payload.get("mode") != "revalidate_action":
            self._schedule_revalidation(decision, anomaly)
        self.telemetry.emit(
            "ontology_agent_run_once",
            {
                "agent": AGENT_SLUG,
                "action_type": decision.action.type,
                "priority": decision.action.priority,
                "primary_signal": decision.projected_ROI_95_CI.primary_signal,
                "roi_expected": decision.projected_ROI_95_CI.expected,
                "event_id": event_id,
            },
        )
        return decision.model_dump(mode="json")

    def run_loop(self, interval_seconds: Optional[int] = None) -> None:
        sleep_for = interval_seconds or self.heartbeat_interval_seconds
        while True:
            self.run_once({})
            time.sleep(sleep_for)

    def _require_supabase(self) -> None:
        if not self.supabase_url or not self.supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    def _headers(self, *, return_representation: bool = False) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }
        if return_representation:
            headers["Prefer"] = "return=representation,resolution=merge-duplicates"
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = f"{self.supabase_url}/rest/v1/{path.lstrip('/')}"
        timeout = kwargs.pop("timeout", 30)
        headers = kwargs.pop("headers", self._headers())
        return self.session.request(method, url, headers=headers, timeout=timeout, **kwargs)

    def _safe_select(self, table: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        response = self._request("get", table, params=params)
        if response.status_code in {400, 404}:
            self.telemetry.emit(
                "ontology_agent_optional_table_missing",
                {"table": table, "status_code": response.status_code},
            )
            return []
        response.raise_for_status()
        body = response.json()
        return body if isinstance(body, list) else []

    def _safe_insert(
        self,
        table: str,
        record: Dict[str, Any],
        *,
        return_representation: bool = False,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        response = self._request(
            "post",
            table,
            params=params,
            headers=self._headers(return_representation=return_representation),
            data=json.dumps(record),
        )
        if response.status_code in {400, 404}:
            self.telemetry.emit(
                "ontology_agent_optional_insert_skipped",
                {"table": table, "status_code": response.status_code},
            )
            return []
        response.raise_for_status()
        if not return_representation:
            return []
        body = response.json()
        return body if isinstance(body, list) else []

    def _poll_supabase(self, *, limit: int) -> Dict[str, Any]:
        ontology_rows = self._safe_select(
            self.ontology_table,
            params={
                "select": (
                    "id,entity,attributes,causal_relations,quantitative_thresholds,"
                    "statistical_confidence,self_correction_triggers,"
                    "derivative_intelligence_hooks,updated_at,confidence"
                ),
                "order": "updated_at.desc",
                "limit": str(limit),
            },
        )
        task_rows = self._safe_select(
            self.tasks_table,
            params={
                "select": "id,type,status,payload_json,scheduled_for,created_at",
                "status": "in.(queued,running)",
                "order": "scheduled_for.asc",
                "limit": str(limit),
            },
        )
        heartbeat_rows = self._safe_select(
            self.heartbeats_table,
            params={
                "select": "id,agent_slug,status,created_at,updated_at,payload_json",
                "order": "created_at.desc",
                "limit": str(limit),
            },
        )
        outbox_rows = self._safe_select(
            self.outbox_table,
            params={
                "select": "event_id,aggregate_type,aggregate_id,entity_key,payload_delta,created_at,published_at",
                "published_at": "is.null",
                "order": "created_at.asc",
                "limit": str(limit),
            },
        )
        return {
            "ontology_nodes": ontology_rows,
            "tasks": task_rows,
            "heartbeats": heartbeat_rows,
            "outbox": outbox_rows,
        }

    def _clean_and_link(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        nodes = [self._normalize_node(row) for row in snapshot.get("ontology_nodes", [])]
        tasks = [self._normalize_task(row) for row in snapshot.get("tasks", [])]
        heartbeats = [self._normalize_heartbeat(row) for row in snapshot.get("heartbeats", [])]
        outbox = [self._normalize_outbox(row) for row in snapshot.get("outbox", [])]

        non_vanity_nodes = [
            node
            for node in nodes
            if str(node.attributes.get("metric_name", node.entity)).strip().lower() not in VANITY_METRICS
        ]
        stale_heartbeats = [
            hb
            for hb in heartbeats
            if hb["ts"] < datetime.now(timezone.utc) - timedelta(seconds=self.heartbeat_interval_seconds * 2)
        ]
        low_conf_nodes = [
            node
            for node in non_vanity_nodes
            if node.statistical_confidence < self.action_success_rate_min
            or float(node.attributes.get("causal_prediction_error", 0.0)) > self.causal_prediction_error_max
        ]
        queued_tasks = [task for task in tasks if task["status"] == "queued"]
        running_tasks = [task for task in tasks if task["status"] == "running"]
        unpublished_outbox = [record for record in outbox if record["published_at"] is None]

        candidate_nodes = self._build_candidate_nodes(
            queued_tasks=queued_tasks,
            running_tasks=running_tasks,
            stale_heartbeats=stale_heartbeats,
            unpublished_outbox=unpublished_outbox,
            low_conf_nodes=low_conf_nodes,
        )
        return {
            "nodes": non_vanity_nodes,
            "tasks": tasks,
            "heartbeats": heartbeats,
            "outbox": outbox,
            "queued_tasks": queued_tasks,
            "running_tasks": running_tasks,
            "stale_heartbeats": stale_heartbeats,
            "unpublished_outbox": unpublished_outbox,
            "low_conf_nodes": low_conf_nodes,
            "candidate_nodes": candidate_nodes,
        }

    def _normalize_node(self, row: Dict[str, Any]) -> StandardizedNode:
        attributes = self._coerce_mapping(row.get("attributes"))
        thresholds = self._coerce_mapping(row.get("quantitative_thresholds"))
        relations = self._normalize_relations(row.get("causal_relations"))
        confidence = self._coerce_float(
            row.get("statistical_confidence", row.get("confidence", 0.95)),
            default=0.95,
        )
        live_graph = self._infer_live_graph(str(row.get("entity", "")), attributes)
        node = StandardizedNode(
            entity=str(row.get("entity") or "unknown_entity"),
            attributes=attributes,
            causal_relations=relations,
            quantitative_thresholds=thresholds,
            statistical_confidence=confidence,
            self_correction_triggers=self._coerce_list(row.get("self_correction_triggers")),
            derivative_intelligence_hooks=self._coerce_mapping(row.get("derivative_intelligence_hooks")),
            direct_ROI_projection_link_to_primary_signal_metrics=SIGNAL_METRICS[:4],
            confidence=confidence,
            live_graph=live_graph,
            roi_hook=f"lift_{live_graph.lower().replace(' ', '_')}",
        )
        return node

    def _normalize_relations(self, raw: Any) -> List[CausalRelation]:
        items = self._coerce_list(raw)
        relations: List[CausalRelation] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            relations.append(
                CausalRelation(
                    source=str(item.get("source") or item.get("from") or "unknown_source"),
                    target=str(item.get("target") or item.get("to") or "unknown_target"),
                    weight=self._coerce_float(item.get("weight"), default=0.25),
                    confidence=self._coerce_float(item.get("confidence"), default=0.9),
                    lag_seconds=int(self._coerce_float(item.get("lag_seconds"), default=0.0)),
                    evidence=str(item.get("evidence") or "runtime"),
                )
            )
        return relations

    def _normalize_task(self, row: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._coerce_mapping(row.get("payload_json"))
        return {
            "id": str(row.get("id") or ""),
            "type": str(row.get("type") or "unknown"),
            "status": str(row.get("status") or "queued"),
            "payload": payload,
            "live_graph": self._infer_live_graph(str(row.get("type") or ""), payload),
            "scheduled_for": self._parse_ts(row.get("scheduled_for")) or datetime.now(timezone.utc),
        }

    def _normalize_heartbeat(self, row: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._coerce_mapping(row.get("payload_json"))
        return {
            "id": str(row.get("id") or ""),
            "agent_slug": str(row.get("agent_slug") or payload.get("agent_slug") or "unknown"),
            "status": str(row.get("status") or payload.get("status") or "ok"),
            "payload": payload,
            "ts": self._parse_ts(row.get("updated_at") or row.get("created_at")) or datetime.now(timezone.utc),
        }

    def _normalize_outbox(self, row: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._coerce_mapping(row.get("payload_delta"))
        return {
            "event_id": str(row.get("event_id") or ""),
            "aggregate_type": str(row.get("aggregate_type") or "unknown"),
            "aggregate_id": str(row.get("aggregate_id") or ""),
            "entity_key": str(row.get("entity_key") or ""),
            "payload_delta": payload,
            "created_at": self._parse_ts(row.get("created_at")) or datetime.now(timezone.utc),
            "published_at": self._parse_ts(row.get("published_at")),
            "live_graph": self._infer_live_graph(str(row.get("entity_key") or ""), payload),
        }

    def _build_candidate_nodes(
        self,
        *,
        queued_tasks: List[Dict[str, Any]],
        running_tasks: List[Dict[str, Any]],
        stale_heartbeats: List[Dict[str, Any]],
        unpublished_outbox: List[Dict[str, Any]],
        low_conf_nodes: List[StandardizedNode],
    ) -> List[StandardizedNode]:
        backlog_size = len(queued_tasks) + len(running_tasks)
        nodes: List[StandardizedNode] = [
            self._make_node(
                entity="ontology_loop_velocity",
                live_graph="Capacity & Utilization",
                attributes={
                    "queued_tasks": len(queued_tasks),
                    "running_tasks": len(running_tasks),
                    "backlog_size": backlog_size,
                    "causal_prediction_error": round(min(0.5, backlog_size / 100.0), 4),
                },
                quantitative_thresholds={"loop_hours_max": self.loop_velocity_max_hours, "backlog_size_max": 8},
                relations=[
                    {"source": "task_backlog", "target": "ontology_loop_cycle_time", "weight": 0.82, "confidence": 0.97},
                    {"source": "ontology_loop_cycle_time", "target": "Free Cash Flow (FCF)", "weight": -0.36, "confidence": 0.92},
                ],
                confidence=0.97,
                triggers=["backlog_size > 8", "ontology_loop_cycle_time > 24h"],
                hook="prune_or_relink_queue_sources",
                roi_hook="shrink_gap_to_deploy_below_24h",
            ),
            self._make_node(
                entity="outbox_propagation_latency",
                live_graph="Revenue Cycle",
                attributes={
                    "unpublished_events": len(unpublished_outbox),
                    "causal_prediction_error": round(min(0.5, len(unpublished_outbox) / 80.0), 4),
                },
                quantitative_thresholds={"propagation_seconds_max": self.integration_latency_max_seconds},
                relations=[
                    {"source": "outbox_backlog", "target": "integration_latency", "weight": 0.88, "confidence": 0.98},
                    {"source": "integration_latency", "target": "action_success_rate", "weight": -0.44, "confidence": 0.94},
                ],
                confidence=0.98,
                triggers=["unpublished_events > 0", "integration_latency > 60s"],
                hook="drain_outbox_and_relink_dependents",
                roi_hook="restore_under_60s_signal_propagation",
            ),
            self._make_node(
                entity="peer_agent_heartbeat_coherence",
                live_graph="Patient Journey",
                attributes={
                    "stale_heartbeats": len(stale_heartbeats),
                    "causal_prediction_error": round(min(0.5, len(stale_heartbeats) / 40.0), 4),
                },
                quantitative_thresholds={"stale_heartbeat_max": 0},
                relations=[
                    {"source": "stale_heartbeats", "target": "hive_coherence", "weight": -0.79, "confidence": 0.96},
                    {"source": "hive_coherence", "target": "action_success_rate", "weight": 0.48, "confidence": 0.91},
                ],
                confidence=0.96,
                triggers=["stale_heartbeats > 0"],
                hook="refresh_missing_hive_signals",
                roi_hook="tighten_hive_propagation",
            ),
            self._make_node(
                entity="node_statistical_integrity",
                live_graph="Clinical Protocols (DAGs)",
                attributes={
                    "low_confidence_nodes": len(low_conf_nodes),
                    "rare_edge_detected": any(
                        bool(node.attributes.get("rare_edge")) or node.live_graph == "Clinical Protocols (DAGs)"
                        for node in low_conf_nodes
                    ),
                    "causal_prediction_error": round(
                        max(
                            [float(node.attributes.get("causal_prediction_error", 0.0)) for node in low_conf_nodes] or [0.0]
                        ),
                        4,
                    ),
                },
                quantitative_thresholds={
                    "statistical_confidence_min": self.action_success_rate_min,
                    "causal_prediction_error_max": self.causal_prediction_error_max,
                },
                relations=[
                    {"source": "low_confidence_nodes", "target": "action_success_rate", "weight": -0.63, "confidence": 0.95},
                    {"source": "action_success_rate", "target": "Scaling multiplier", "weight": 0.57, "confidence": 0.9},
                ],
                confidence=0.95,
                triggers=["statistical_confidence < 0.98", "causal_prediction_error > 0.02"],
                hook="prune_or_clinical_gate_low_signal_nodes",
                roi_hook="protect_downstream_action_success",
            ),
        ]
        return nodes

    def _make_node(
        self,
        *,
        entity: str,
        live_graph: str,
        attributes: Dict[str, Any],
        quantitative_thresholds: Dict[str, Any],
        relations: Iterable[Dict[str, Any]],
        confidence: float,
        triggers: List[str],
        hook: str,
        roi_hook: str,
    ) -> StandardizedNode:
        return StandardizedNode(
            entity=entity,
            attributes=attributes,
            causal_relations=[CausalRelation(**relation) for relation in relations],
            quantitative_thresholds=quantitative_thresholds,
            statistical_confidence=confidence,
            self_correction_triggers=triggers,
            derivative_intelligence_hooks={
                "sandbox_simulation": "digital_twin.counterfactual",
                "least_action_mode": True,
                "hook": hook,
            },
            direct_ROI_projection_link_to_primary_signal_metrics=SIGNAL_METRICS[:6],
            confidence=confidence,
            live_graph=live_graph,
            roi_hook=roi_hook,
        )

    def _select_highest_leverage_anomaly(self, cleaned: Dict[str, Any]) -> Dict[str, Any]:
        candidates: List[Dict[str, Any]] = []
        for node in cleaned["candidate_nodes"]:
            severity = self._calculate_gap_severity(node)
            if severity <= 0:
                continue
            causal_score = sum(abs(relation.weight) * relation.confidence for relation in node.causal_relations)
            score = round(severity * causal_score * node.statistical_confidence, 6)
            candidates.append(
                {
                    "entity": node.entity,
                    "live_graph": node.live_graph,
                    "severity": severity,
                    "score": score,
                    "rare_edge_detected": bool(node.attributes.get("rare_edge_detected")),
                    "confidence": node.statistical_confidence,
                    "attributes": node.attributes,
                }
            )
        if not candidates:
            return {
                "entity": "steady_state",
                "live_graph": "Capacity & Utilization",
                "severity": 0.05,
                "score": 0.05,
                "rare_edge_detected": False,
                "confidence": 0.99,
                "attributes": {"mode": "observe"},
            }
        candidates.sort(key=lambda item: item["score"], reverse=True)
        return candidates[0]

    def _calculate_gap_severity(self, node: StandardizedNode) -> float:
        attributes = node.attributes
        if node.entity == "ontology_loop_velocity":
            backlog_size = float(attributes.get("backlog_size", 0.0))
            return min(1.0, max(0.0, (backlog_size - 8.0) / 8.0 + 0.2))
        if node.entity == "outbox_propagation_latency":
            unpublished = float(attributes.get("unpublished_events", 0.0))
            return min(1.0, unpublished / 12.0)
        if node.entity == "peer_agent_heartbeat_coherence":
            stale = float(attributes.get("stale_heartbeats", 0.0))
            return min(1.0, stale / 6.0)
        if node.entity == "node_statistical_integrity":
            low_conf = float(attributes.get("low_confidence_nodes", 0.0))
            prediction_error = float(attributes.get("causal_prediction_error", 0.0))
            return min(1.0, max(low_conf / 5.0, prediction_error / max(self.causal_prediction_error_max, 0.0001)))
        return 0.0

    def _build_decision(self, anomaly: Dict[str, Any], cleaned: Dict[str, Any]) -> StrictAgentOutput:
        if anomaly["entity"] == "node_statistical_integrity":
            if anomaly["rare_edge_detected"]:
                action = ActionSpec(
                    type="ontology.request_clinical_quality_gate",
                    title="Hold rare-edge pruning behind Clinical Quality gate",
                    live_graph=anomaly["live_graph"],
                    priority="p0",
                    payload={
                        "candidate_node_count": int(anomaly["attributes"].get("low_confidence_nodes", 0)),
                        "mode": "clinical_quality_gate",
                        "human_input_budget_ratio_max": self.human_input_budget_ratio_max,
                    },
                )
                primary_signal = "Action success rate (>=98%)"
            else:
                action = ActionSpec(
                    type="ontology.prune_and_relink",
                    title="Kill statistically weak ontology nodes and relink causal edges",
                    live_graph=anomaly["live_graph"],
                    priority="p0",
                    payload={
                        "candidate_node_count": int(anomaly["attributes"].get("low_confidence_nodes", 0)),
                        "prediction_error_max": self.causal_prediction_error_max,
                        "mode": "staged_iac_deploy",
                    },
                )
                primary_signal = "Causal prediction error (<2%)"
        elif anomaly["entity"] == "outbox_propagation_latency":
            action = ActionSpec(
                type="ontology.flush_hive_outbox",
                title="Drain propagation backlog and relink delayed downstream consumers",
                live_graph=anomaly["live_graph"],
                priority="p0",
                payload={
                    "unpublished_events": int(anomaly["attributes"].get("unpublished_events", 0)),
                    "propagation_seconds_max": self.integration_latency_max_seconds,
                    "mode": "staged_iac_deploy",
                },
            )
            primary_signal = "Action success rate (>=98%)"
        elif anomaly["entity"] == "ontology_loop_velocity":
            action = ActionSpec(
                type="ontology.rebalance_loop_velocity",
                title="Reprioritize backlog, prune vanity paths, and tighten loop cadence",
                live_graph=anomaly["live_graph"],
                priority="p0" if anomaly["severity"] >= 0.4 else "p1",
                payload={
                    "queued_tasks": int(anomaly["attributes"].get("queued_tasks", 0)),
                    "running_tasks": int(anomaly["attributes"].get("running_tasks", 0)),
                    "loop_hours_max": self.loop_velocity_max_hours,
                    "mode": "staged_iac_deploy",
                },
            )
            primary_signal = "Ontology loop cycle time"
        elif anomaly["entity"] == "peer_agent_heartbeat_coherence":
            action = ActionSpec(
                type="ontology.restore_hive_heartbeat_coherence",
                title="Refresh stale peer heartbeats and republish missing signals",
                live_graph=anomaly["live_graph"],
                priority="p1",
                payload={
                    "stale_heartbeats": int(anomaly["attributes"].get("stale_heartbeats", 0)),
                    "propagation_seconds_max": self.integration_latency_max_seconds,
                    "mode": "staged_iac_deploy",
                },
            )
            primary_signal = "Scaling multiplier"
        else:
            action = ActionSpec(
                type="ontology.observe_and_hold",
                title="Hold steady-state and keep measuring attribution",
                live_graph="Capacity & Utilization",
                priority="p2",
                payload={"mode": "observe"},
            )
            primary_signal = "Contribution Margin"

        projection = self._simulate_digital_twin(anomaly, primary_signal=primary_signal)
        validation_plan = [
            ValidationCheck(
                metric="Ontology loop cycle time",
                target=f"<= {self.loop_velocity_max_hours}h",
                window="next 1-2 heartbeats",
            ),
            ValidationCheck(
                metric="Action success rate",
                target=f">= {self.action_success_rate_min:.2f}",
                window="next 20 downstream actions",
            ),
            ValidationCheck(
                metric="Integration latency",
                target=f"<= {self.integration_latency_max_seconds}s",
                window="next 3 outbox propagation windows",
            ),
        ]
        kill_criteria = [
            KillCriterion(
                metric="Action success rate",
                threshold=f"< {self.action_success_rate_min:.2f}",
                reason="Kill any node or rollout that reduces downstream action reliability.",
            ),
            KillCriterion(
                metric="Causal prediction error",
                threshold=f"> {self.causal_prediction_error_max:.2f}",
                reason="Prune interventions that fail first-principles predictive accuracy.",
            ),
            KillCriterion(
                metric="Contribution Margin",
                threshold="< baseline after 2 heartbeats",
                reason="Terminate ontology changes that drag unit economics.",
            ),
        ]
        return StrictAgentOutput(
            action=action,
            projected_ROI_95_CI=projection,
            validation_plan=validation_plan,
            kill_criteria=kill_criteria,
        )

    def _simulate_digital_twin(self, anomaly: Dict[str, Any], *, primary_signal: str) -> ROIProjection95CI:
        # Counterfactual intervention score approximates a do(X=x) move using weighted causal gaps.
        severity = float(anomaly.get("severity", 0.0))
        confidence = float(anomaly.get("confidence", 0.95))
        expected = max(0.01, round(severity * (0.9 + confidence), 4))
        spread = max(0.02, round((1.0 - confidence) * 0.5 + 0.08, 4))
        lower = max(0.0, round(expected - spread, 4))
        upper = round(expected + spread, 4)
        return ROIProjection95CI(
            lower=lower,
            expected=expected,
            upper=upper,
            unit="projected_primary_signal_uplift_ratio",
            primary_signal=primary_signal,
            confidence=confidence,
        )

    def _upsert_candidate_nodes(self, nodes: List[StandardizedNode]) -> None:
        for node in nodes:
            record = node.model_dump(mode="json")
            record["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._safe_insert(
                self.ontology_table,
                record,
                params={"on_conflict": "entity"},
            )

    def _publish_outbox_signal(self, decision: StrictAgentOutput, anomaly: Dict[str, Any]) -> str:
        payload = {
            "agent_slug": AGENT_SLUG,
            "entity": anomaly["entity"],
            "action": decision.action.model_dump(mode="json"),
            "projected_ROI_95_CI": decision.projected_ROI_95_CI.model_dump(mode="json"),
            "validation_plan": [item.model_dump(mode="json") for item in decision.validation_plan],
            "kill_criteria": [item.model_dump(mode="json") for item in decision.kill_criteria],
        }
        envelope = build_outbox_envelope(
            mutation_key=f"{AGENT_SLUG}:{anomaly['entity']}:{decision.action.type}",
            aggregate_type="ontology_signal",
            aggregate_id=anomaly["entity"],
            payload_delta=payload,
            schema_version=1,
        )
        self._safe_insert(self.outbox_table, envelope.as_record())
        return envelope.event_id

    def _record_heartbeat(self, decision: StrictAgentOutput, anomaly: Dict[str, Any], *, event_id: str) -> None:
        payload = {
            "agent_slug": AGENT_SLUG,
            "agent_title": AGENT_TITLE,
            "status": "ok",
            "event_id": event_id,
            "anomaly": anomaly,
            "decision": decision.model_dump(mode="json"),
        }
        heartbeat_record = {
            "agent_slug": AGENT_SLUG,
            "status": "ok",
            "payload_json": payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._safe_insert(self.heartbeats_table, heartbeat_record)
        target = state_path("runtime", "heartbeats", f"{AGENT_SLUG}.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _schedule_revalidation(self, decision: StrictAgentOutput, anomaly: Dict[str, Any]) -> None:
        scheduled_for = (datetime.now(timezone.utc) + timedelta(seconds=self.heartbeat_interval_seconds)).isoformat()
        payload = {
            "mode": "revalidate_action",
            "source_agent": AGENT_SLUG,
            "candidate_action": decision.action.model_dump(mode="json"),
            "anomaly_entity": anomaly["entity"],
            "idempotency_key": f"{AGENT_SLUG}:{decision.action.type}:{anomaly['entity']}:{scheduled_for[:16]}",
        }
        task = {
            "type": "ontology.chief.run",
            "payload_json": payload,
            "status": "queued",
            "scheduled_for": scheduled_for,
            "retries": 0,
            "max_retries": 3,
        }
        self._safe_insert(self.tasks_table, task)

    def _infer_live_graph(self, label: str, payload: Dict[str, Any]) -> str:
        combined = f"{label} {json.dumps(payload, ensure_ascii=True).lower()}".lower()
        if any(token in combined for token in ("appointment", "patient", "journey", "retention")):
            return "Patient Journey"
        if any(token in combined for token in ("ar", "billing", "cash", "revenue", "collection", "outbox")):
            return "Revenue Cycle"
        if any(token in combined for token in ("clinical", "protocol", "provider", "quality")):
            return "Clinical Protocols (DAGs)"
        if any(token in combined for token in ("capacity", "utilization", "chair", "queue", "backlog")):
            return "Capacity & Utilization"
        return "Regulatory & Geo Constraints"

    def _coerce_mapping(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {"value": value}
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        return {}

    def _coerce_list(self, value: Any) -> List[Any]:
        if isinstance(value, list):
            return list(value)
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return [value]
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        return []

    def _coerce_float(self, value: Any, *, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _parse_ts(self, value: Any) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None


def main() -> int:
    agent = ChiefOntologyDerivativeIntelligenceArchitectAgent()
    print(json.dumps(agent.run_once({}), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
