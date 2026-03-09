"""
Head of Clinical Quality Control — L5 Agent Core
=================================================
Owns causal clinical governance, protocol ontology execution,
and real-time risk elimination across dental, medspa, and
plastic surgery verticals.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Dict, List

from agents.l5.base import (
    ActionOutput,
    ConfidenceInterval,
    L5AgentBase,
    OntologyNode,
    OutboxMessage,
)

logger = logging.getLogger("eve.l5.head-clinical-quality")

# ---------------------------------------------------------------------------
# Thresholds & constants
# ---------------------------------------------------------------------------

COMPLICATION_RATE_MAX = 0.008
PROTOCOL_ADHERENCE_MIN = 0.98
PROVIDER_UTILIZATION_MIN = 0.92
ADVERSE_EVENT_RESOLUTION_SLA_H = 72


class HeadClinicalQualityAgent(L5AgentBase):
    """L5 autonomous agent for clinical quality control."""

    role_id: ClassVar[str] = "head-clinical-quality"
    display_name: ClassVar[str] = "Head of Clinical Quality Control"
    cadence_seconds: ClassVar[int] = 60
    poll_tables: ClassVar[List[str]] = [
        "ontology_nodes",
        "tasks",
        "heartbeats",
        "outbox",
    ]
    vanity_metrics: ClassVar[List[str]] = [
        "subjective_satisfaction",
        "raw_volume",
        "unvalidated_symmetry",
        "regulatory_checkbox",
        "anecdotal_report",
    ]
    signal_metrics: ClassVar[List[str]] = [
        "risk_adjusted_complication_rate",
        "validated_proms_delta",
        "procedure_success_rate",
        "protocol_adherence",
        "quality_gated_provider_utilization",
        "adverse_event_resolution_velocity",
    ]

    # -- Pipeline stages ----------------------------------------------------

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []
        nodes = data.get("ontology_nodes", [])

        for node in nodes:
            attrs = node.get("attributes", {})

            complication_rate = attrs.get("complication_rate")
            if complication_rate is not None and complication_rate > COMPLICATION_RATE_MAX:
                anomalies.append({
                    "type": "complication_rate_spike",
                    "entity": node.get("entity"),
                    "value": complication_rate,
                    "threshold": COMPLICATION_RATE_MAX,
                    "severity": "critical",
                })

            adherence = attrs.get("protocol_adherence")
            if adherence is not None and adherence < PROTOCOL_ADHERENCE_MIN:
                anomalies.append({
                    "type": "protocol_adherence_drop",
                    "entity": node.get("entity"),
                    "value": adherence,
                    "threshold": PROTOCOL_ADHERENCE_MIN,
                    "severity": "high",
                })

            utilization = attrs.get("provider_utilization")
            if utilization is not None and utilization < PROVIDER_UTILIZATION_MIN:
                anomalies.append({
                    "type": "provider_utilization_anomaly",
                    "entity": node.get("entity"),
                    "value": utilization,
                    "threshold": PROVIDER_UTILIZATION_MIN,
                    "severity": "medium",
                })

        tasks = data.get("tasks", [])
        for task in tasks:
            if (
                task.get("status") == "pending"
                and "adverse_event" in task.get("title", "").lower()
            ):
                anomalies.append({
                    "type": "adverse_event_unresolved",
                    "task_id": task.get("task_id"),
                    "title": task.get("title"),
                    "severity": "high",
                })

        if anomalies:
            logger.info("Detected %d anomalies", len(anomalies))
        return anomalies

    def derive_intelligence(
        self, anomalies: List[Dict], data: Dict[str, List[Dict]]
    ) -> List[ActionOutput]:
        actions: List[ActionOutput] = []

        for anomaly in anomalies:
            atype = anomaly.get("type", "")

            if atype == "complication_rate_spike":
                actions.append(ActionOutput(
                    action=(
                        f"Initiate protocol review for {anomaly['entity']}; "
                        f"complication rate {anomaly['value']:.4f} exceeds "
                        f"threshold {anomaly['threshold']}"
                    ),
                    projected_roi=2.5,
                    roi_ci=ConfidenceInterval(lower=1.2, upper=4.0),
                    validation_plan=(
                        "Compare 30-day post-intervention complication rate "
                        "against pre-intervention baseline using paired t-test"
                    ),
                    kill_criteria=(
                        "Revert if complication rate does not decrease by ≥20% "
                        "within 30 days or if provider throughput drops >15%"
                    ),
                ))

            elif atype == "protocol_adherence_drop":
                actions.append(ActionOutput(
                    action=(
                        f"Deploy targeted protocol reinforcement for "
                        f"{anomaly['entity']}; adherence at "
                        f"{anomaly['value']:.2%} vs {anomaly['threshold']:.2%} target"
                    ),
                    projected_roi=1.8,
                    roi_ci=ConfidenceInterval(lower=0.9, upper=3.0),
                    validation_plan=(
                        "Monitor daily adherence scores for 14 days; "
                        "validate with direct observation audits"
                    ),
                    kill_criteria=(
                        "Revert if adherence does not reach 98% within 14 days "
                        "or if provider satisfaction drops below baseline"
                    ),
                ))

            elif atype == "provider_utilization_anomaly":
                actions.append(ActionOutput(
                    action=(
                        f"Investigate underutilization for {anomaly['entity']}; "
                        f"utilization at {anomaly['value']:.2%}"
                    ),
                    projected_roi=1.5,
                    roi_ci=ConfidenceInterval(lower=0.5, upper=2.8),
                    validation_plan=(
                        "Cross-reference with scheduling data and provider "
                        "credentialing status; 7-day follow-up"
                    ),
                    kill_criteria=(
                        "Deprioritize if root cause is external "
                        "(e.g., provider leave, seasonal demand shift)"
                    ),
                ))

            elif atype == "adverse_event_unresolved":
                actions.append(ActionOutput(
                    action=(
                        f"Escalate unresolved adverse event: {anomaly['title']}"
                    ),
                    projected_roi=3.0,
                    roi_ci=ConfidenceInterval(lower=1.5, upper=5.0),
                    validation_plan=(
                        "Track event through resolution state machine; "
                        "confirm closure within SLA"
                    ),
                    kill_criteria=(
                        "Cancel escalation if event is reclassified as "
                        "non-adverse after clinical review"
                    ),
                ))

        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for action in actions:
            event_type = "quality_alert"
            if "protocol review" in action.action.lower():
                event_type = "protocol_version_update"
            elif "adverse event" in action.action.lower():
                event_type = "adverse_event_closure"

            self.publish(
                event_type=event_type,
                payload=action.model_dump(),
            )
            logger.info(
                "Emitted %s: %s (ROI CI [%.2f, %.2f])",
                event_type,
                action.action[:80],
                action.roi_ci.lower,
                action.roi_ci.upper,
            )
