"""Chief Ontology & Derivative Intelligence Architect — Eve L5 Agent."""

from __future__ import annotations

import logging
import statistics
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel, Field

from agents.l5.base import (
    ActionOutput,
    ConfidenceInterval,
    L5AgentBase,
    OntologyNode,
)

logger = logging.getLogger("eve.l5.ontology_architect")


class CausalRelation(BaseModel):
    source: str
    target: str
    weight: float = 1.0
    direction: str = "forward"
    confidence: float = 0.95
    mechanism: str = ""


class OntologyGapReport(BaseModel):
    gap_id: str
    entity: str
    missing_fields: List[str]
    severity: float
    estimated_roi_of_fix: float


class ChiefOntologyArchitect(L5AgentBase):
    role_id: ClassVar[str] = "chief-ontology-architect"
    display_name: ClassVar[str] = "Chief Ontology & Derivative Intelligence Architect"
    cadence_seconds: ClassVar[int] = 120
    poll_tables: ClassVar[List[str]] = ["ontology_nodes", "tasks", "heartbeats", "outbox"]

    vanity_metrics: ClassVar[List[str]] = [
        "Gross Revenue", "Headcount", "EBITDA (Adj)", "Market Share",
        "R&D Spend", "Followers", "Likes", "Brand Awareness",
        "Verbal Commitments", "Networking", "Body Weight",
        "Subjective Feeling", "Aesthetic Symmetry", "Static taxonomies",
        "Philosophical models", "Diagram beauty", "Node count",
    ]

    signal_metrics: ClassVar[List[str]] = [
        "FCF", "Rev/Employee", "LTV:CAC payback", "Contribution Margin",
        "Chair Utilization", "Conversion Velocity", "Referral Rate",
        "Ontology loop cycle time", "Action success rate",
        "Self-correction hit rate", "Causal prediction error",
        "Scaling multiplier",
    ]

    REQUIRED_NODE_FIELDS = [
        "entity", "attributes", "causal_relations",
        "quantitative_thresholds", "statistical_confidence",
        "self_correction_triggers", "derivative_intelligence_hooks",
        "roi_projection_link",
    ]

    LOOP_VELOCITY_MAX_HOURS = 24
    ACTION_SUCCESS_MIN = 0.98
    CAUSAL_PREDICTION_ERROR_MAX = 0.02
    NOVEL_SCENARIO_BUDGET = 0.15

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []
        nodes = data.get("ontology_nodes", [])

        for node in nodes:
            missing = [f for f in self.REQUIRED_NODE_FIELDS if not node.get(f)]
            if missing:
                anomalies.append({
                    "type": "incomplete_node",
                    "node_id": node.get("node_id", "unknown"),
                    "entity": node.get("entity", "unknown"),
                    "missing_fields": missing,
                    "severity": len(missing) / len(self.REQUIRED_NODE_FIELDS),
                })

            conf = node.get("statistical_confidence", 0)
            if isinstance(conf, (int, float)) and conf < 0.90:
                anomalies.append({
                    "type": "low_confidence",
                    "node_id": node.get("node_id", "unknown"),
                    "confidence": conf,
                    "severity": 1.0 - conf,
                })

        heartbeats = data.get("heartbeats", [])
        if heartbeats:
            success_rates = [
                h.get("actions_emitted", 0) / max(h.get("anomalies_detected", 1), 1)
                for h in heartbeats
            ]
            avg_success = statistics.mean(success_rates) if success_rates else 1.0
            if avg_success < self.ACTION_SUCCESS_MIN:
                anomalies.append({
                    "type": "action_success_below_threshold",
                    "current_rate": avg_success,
                    "threshold": self.ACTION_SUCCESS_MIN,
                    "severity": self.ACTION_SUCCESS_MIN - avg_success,
                })

        return anomalies

    def derive_intelligence(self, anomalies: List[Dict], data: Dict[str, List[Dict]]) -> List[ActionOutput]:
        actions: List[ActionOutput] = []

        incomplete = [a for a in anomalies if a["type"] == "incomplete_node"]
        if incomplete:
            top = sorted(incomplete, key=lambda x: x["severity"], reverse=True)[:5]
            for gap in top:
                roi_estimate = gap["severity"] * 10_000
                actions.append(ActionOutput(
                    action=f"ENRICH_NODE:{gap['node_id']}:fill_fields={gap['missing_fields']}",
                    projected_roi=roi_estimate,
                    roi_ci=ConfidenceInterval(lower=roi_estimate * 0.7, upper=roi_estimate * 1.3),
                    validation_plan=f"Re-poll node {gap['node_id']} after enrichment; verify all {len(self.REQUIRED_NODE_FIELDS)} fields present",
                    kill_criteria=f"Node still missing >{len(gap['missing_fields'])//2} fields after 2 enrichment cycles",
                ))

        low_conf = [a for a in anomalies if a["type"] == "low_confidence"]
        if low_conf:
            for lc in sorted(low_conf, key=lambda x: x["severity"], reverse=True)[:3]:
                actions.append(ActionOutput(
                    action=f"RECALIBRATE_NODE:{lc['node_id']}:current_conf={lc['confidence']:.2f}",
                    projected_roi=lc["severity"] * 5_000,
                    roi_ci=ConfidenceInterval(
                        lower=lc["severity"] * 3_500,
                        upper=lc["severity"] * 7_000,
                    ),
                    validation_plan=f"Statistical confidence must reach >=0.95 within 24h",
                    kill_criteria=f"Confidence delta <0.02 after 3 recalibration cycles — prune node",
                ))

        success_anomalies = [a for a in anomalies if a["type"] == "action_success_below_threshold"]
        for sa in success_anomalies:
            actions.append(ActionOutput(
                action=f"SYSTEM_RECALIBRATE:action_success={sa['current_rate']:.3f}",
                projected_roi=50_000,
                roi_ci=ConfidenceInterval(lower=30_000, upper=80_000),
                validation_plan="Monitor action success rate over next 50 ticks; must exceed 98%",
                kill_criteria="Rate fails to recover above 95% after 100 ticks — escalate to all agents",
            ))

        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for act in actions:
            self.publish(
                event_type="ontology_action",
                payload=act.model_dump(),
            )
            if "ENRICH_NODE" in act.action:
                node_id = act.action.split(":")[1]
                self.create_task(
                    title=f"Enrich ontology node {node_id}",
                    description=act.action,
                    priority=1,
                )
            logger.info("[%s] emitted: %s", self.role_id, act.action)

    def validate_hypergraph_integrity(self, nodes: List[Dict]) -> Dict[str, Any]:
        total = len(nodes)
        complete = sum(
            1 for n in nodes
            if all(n.get(f) for f in self.REQUIRED_NODE_FIELDS)
        )
        orphans = [
            n for n in nodes
            if not n.get("causal_relations")
        ]
        return {
            "total_nodes": total,
            "complete_nodes": complete,
            "completeness_rate": complete / max(total, 1),
            "orphan_nodes": len(orphans),
            "integrity_score": complete / max(total, 1) * (1 - len(orphans) / max(total, 1)),
        }

    def simulate_sandbox(self, node: OntologyNode, intervention: Dict) -> Dict[str, float]:
        base_roi = intervention.get("estimated_roi", 0)
        return {
            "simulated_roi": base_roi * 0.85,
            "confidence": 0.90,
            "risk_factor": 0.05,
        }
