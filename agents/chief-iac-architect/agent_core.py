"""
Chief IaC Architect — L5 Agent Core
====================================
Engineers declarative GitOps control plane as self-healing backbone
for L5 autonomous clinic scaling.
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

logger = logging.getLogger("eve.l5.chief-iac-architect")

# ---------------------------------------------------------------------------
# Thresholds & constants
# ---------------------------------------------------------------------------

UPTIME_MIN = 0.9995
P95_LATENCY_MAX_MS = 200
MTTR_MAX_MIN = 5
CHANGE_FAILURE_RATE_MAX = 0.05
CONFIG_DRIFT_TOLERANCE = 0.0
AUTO_REMEDIATION_RATE_MIN = 0.95


class ChiefIaCArchitectAgent(L5AgentBase):
    """L5 autonomous agent for infrastructure-as-code and GitOps."""

    role_id: ClassVar[str] = "chief-iac-architect"
    display_name: ClassVar[str] = "Chief IaC Architect"
    cadence_seconds: ClassVar[int] = 60
    poll_tables: ClassVar[List[str]] = [
        "ontology_nodes",
        "tasks",
        "heartbeats",
        "outbox",
    ]
    vanity_metrics: ClassVar[List[str]] = [
        "lines_of_code",
        "tool_count",
        "gross_spend",
        "hype_score",
        "manual_process_count",
    ]
    signal_metrics: ClassVar[List[str]] = [
        "uptime",
        "p95_latency_ms",
        "clone_velocity_hours",
        "mttr_minutes",
        "change_failure_rate",
        "auto_remediation_rate",
        "human_input_ratio",
        "config_drift_pct",
        "hipaa_enforcement_rate",
    ]

    # -- Pipeline stages ----------------------------------------------------

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []
        nodes = data.get("ontology_nodes", [])

        for node in nodes:
            attrs = node.get("attributes", {})

            drift = attrs.get("config_drift_pct")
            if drift is not None and drift > CONFIG_DRIFT_TOLERANCE:
                anomalies.append({
                    "type": "config_drift",
                    "entity": node.get("entity"),
                    "value": drift,
                    "threshold": CONFIG_DRIFT_TOLERANCE,
                    "severity": "critical",
                })

            uptime = attrs.get("uptime")
            if uptime is not None and uptime < UPTIME_MIN:
                anomalies.append({
                    "type": "uptime_drop",
                    "entity": node.get("entity"),
                    "value": uptime,
                    "threshold": UPTIME_MIN,
                    "severity": "critical",
                })

            latency = attrs.get("p95_latency_ms")
            if latency is not None and latency > P95_LATENCY_MAX_MS:
                anomalies.append({
                    "type": "latency_spike",
                    "entity": node.get("entity"),
                    "value": latency,
                    "threshold": P95_LATENCY_MAX_MS,
                    "severity": "high",
                })

        tasks = data.get("tasks", [])
        for task in tasks:
            if (
                task.get("status") == "failed"
                and "deploy" in task.get("title", "").lower()
            ):
                anomalies.append({
                    "type": "deployment_failure",
                    "task_id": task.get("task_id"),
                    "title": task.get("title"),
                    "severity": "critical",
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

            if atype == "config_drift":
                actions.append(ActionOutput(
                    action=(
                        f"Auto-reconcile config drift on {anomaly['entity']}; "
                        f"drift detected at {anomaly['value']:.4f} "
                        f"(tolerance: {anomaly['threshold']})"
                    ),
                    projected_roi=4.0,
                    roi_ci=ConfidenceInterval(lower=2.0, upper=7.0),
                    validation_plan=(
                        "Post-reconciliation drift scan confirms 0% drift; "
                        "validate with infrastructure diff against GitOps source of truth"
                    ),
                    kill_criteria=(
                        "Rollback if reconciliation causes service degradation "
                        "or uptime drops below 99.95%"
                    ),
                ))

            elif atype == "deployment_failure":
                actions.append(ActionOutput(
                    action=(
                        f"Trigger auto-remediation for failed deployment: "
                        f"{anomaly['title']}"
                    ),
                    projected_roi=3.5,
                    roi_ci=ConfidenceInterval(lower=1.5, upper=6.0),
                    validation_plan=(
                        "Re-deploy with rollback strategy; validate service "
                        "health checks pass within MTTR SLA"
                    ),
                    kill_criteria=(
                        "Abort if second deployment attempt fails; "
                        "escalate to human operator"
                    ),
                ))

            elif atype == "latency_spike":
                actions.append(ActionOutput(
                    action=(
                        f"Investigate and optimize latency for {anomaly['entity']}; "
                        f"p95 at {anomaly['value']}ms vs {anomaly['threshold']}ms target"
                    ),
                    projected_roi=2.0,
                    roi_ci=ConfidenceInterval(lower=0.8, upper=3.5),
                    validation_plan=(
                        "Monitor p95 latency over 1h post-intervention; "
                        "confirm sustained reduction below 200ms"
                    ),
                    kill_criteria=(
                        "Revert if optimization introduces new errors or "
                        "increases p99 latency"
                    ),
                ))

            elif atype == "uptime_drop":
                actions.append(ActionOutput(
                    action=(
                        f"Initiate self-healing sequence for {anomaly['entity']}; "
                        f"uptime at {anomaly['value']:.4f} vs "
                        f"{anomaly['threshold']:.4f} SLA"
                    ),
                    projected_roi=5.0,
                    roi_ci=ConfidenceInterval(lower=2.5, upper=8.0),
                    validation_plan=(
                        "Confirm service restoration via health probes; "
                        "validate uptime recovery over 4h window"
                    ),
                    kill_criteria=(
                        "Escalate to human if self-healing fails after "
                        "3 automated attempts within 15 minutes"
                    ),
                ))

        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for action in actions:
            event_type = "fleet_alert"
            if "drift" in action.action.lower():
                event_type = "iac_deployment_commit"
            elif "remediation" in action.action.lower() or "healing" in action.action.lower():
                event_type = "remediation_trigger"

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
