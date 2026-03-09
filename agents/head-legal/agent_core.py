"""
Head of Legal — L5 Agent Core
==============================
Eradicates preventable legal risk to enable unrestricted scaling.
Covers CPOM compliance, state matrix, consent engines, and
AKS/Stark/HIPAA/FDA enforcement.
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

logger = logging.getLogger("eve.l5.head-legal")

# ---------------------------------------------------------------------------
# Thresholds & constants
# ---------------------------------------------------------------------------

CONSENT_INTEGRITY_MIN = 0.997
CONTRACT_CYCLE_MAX_DAYS = 14
MULTI_JURISDICTION_READINESS_MIN = 0.95
EMV_SPIKE_THRESHOLD = 0.15


class HeadLegalAgent(L5AgentBase):
    """L5 autonomous agent for legal risk elimination and compliance."""

    role_id: ClassVar[str] = "head-legal"
    display_name: ClassVar[str] = "Head of Legal"
    cadence_seconds: ClassVar[int] = 60
    poll_tables: ClassVar[List[str]] = [
        "ontology_nodes",
        "tasks",
        "outbox",
    ]
    vanity_metrics: ClassVar[List[str]] = [
        "review_count",
        "document_length",
        "cya_volume",
    ]
    signal_metrics: ClassVar[List[str]] = [
        "aggregate_emv_reduction",
        "risk_delta_per_onboarding",
        "compliance_cost_pct_revenue",
        "multi_jurisdiction_readiness_score",
        "consent_integrity_rate",
    ]

    # -- Pipeline stages ----------------------------------------------------

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []
        nodes = data.get("ontology_nodes", [])

        for node in nodes:
            attrs = node.get("attributes", {})

            consent_rate = attrs.get("consent_integrity_rate")
            if consent_rate is not None and consent_rate < CONSENT_INTEGRITY_MIN:
                anomalies.append({
                    "type": "consent_gap",
                    "entity": node.get("entity"),
                    "value": consent_rate,
                    "threshold": CONSENT_INTEGRITY_MIN,
                    "severity": "critical",
                })

            cpom_compliant = attrs.get("cpom_compliant")
            if cpom_compliant is not None and not cpom_compliant:
                anomalies.append({
                    "type": "cpom_violation",
                    "entity": node.get("entity"),
                    "jurisdiction": attrs.get("jurisdiction", "unknown"),
                    "severity": "critical",
                })

            reg_change = attrs.get("pending_regulatory_change")
            if reg_change:
                anomalies.append({
                    "type": "regulatory_change",
                    "entity": node.get("entity"),
                    "regulation": reg_change,
                    "severity": "high",
                })

        tasks = data.get("tasks", [])
        for task in tasks:
            if task.get("status") == "pending" and "contract" in task.get("title", "").lower():
                created = task.get("created_at", "")
                anomalies.append({
                    "type": "contract_velocity_delay",
                    "task_id": task.get("task_id"),
                    "title": task.get("title"),
                    "created_at": created,
                    "severity": "medium",
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

            if atype == "consent_gap":
                actions.append(ActionOutput(
                    action=(
                        f"Deploy consent engine patch for {anomaly['entity']}; "
                        f"integrity rate {anomaly['value']:.4f} below "
                        f"{anomaly['threshold']} minimum"
                    ),
                    projected_roi=5.0,
                    roi_ci=ConfidenceInterval(lower=2.5, upper=8.0),
                    validation_plan=(
                        "Audit consent records for 7 days post-patch; "
                        "confirm integrity rate ≥99.7% with independent review"
                    ),
                    kill_criteria=(
                        "Revert patch and halt affected procedures if "
                        "integrity rate does not recover within 48 hours"
                    ),
                ))

            elif atype == "cpom_violation":
                actions.append(ActionOutput(
                    action=(
                        f"Initiate CPOM remediation for {anomaly['entity']} "
                        f"in {anomaly.get('jurisdiction', 'unknown')}; "
                        f"entity structure non-compliant"
                    ),
                    projected_roi=8.0,
                    roi_ci=ConfidenceInterval(lower=4.0, upper=15.0),
                    validation_plan=(
                        "Restructure entity per state CPOM requirements; "
                        "validate with outside counsel review; "
                        "confirm compliance via state regulatory check"
                    ),
                    kill_criteria=(
                        "Halt all operations in jurisdiction if CPOM "
                        "compliance cannot be achieved within 30 days"
                    ),
                ))

            elif atype == "regulatory_change":
                actions.append(ActionOutput(
                    action=(
                        f"Update regulatory ontology for {anomaly['entity']}; "
                        f"new regulation: {anomaly.get('regulation', 'unspecified')}"
                    ),
                    projected_roi=3.0,
                    roi_ci=ConfidenceInterval(lower=1.5, upper=5.0),
                    validation_plan=(
                        "Map regulation to affected entities and workflows; "
                        "implement compliance-as-code changes; "
                        "validate with legal team review"
                    ),
                    kill_criteria=(
                        "Revert if regulation is withdrawn, stayed, or "
                        "superseded before effective date"
                    ),
                ))

            elif atype == "contract_velocity_delay":
                actions.append(ActionOutput(
                    action=(
                        f"Accelerate contract pipeline: {anomaly['title']}"
                    ),
                    projected_roi=1.5,
                    roi_ci=ConfidenceInterval(lower=0.5, upper=3.0),
                    validation_plan=(
                        "Track contract from current stage to execution; "
                        "confirm cycle time ≤14 days; "
                        "identify and remove bottleneck"
                    ),
                    kill_criteria=(
                        "Deprioritize if delay is caused by external party "
                        "unresponsiveness beyond agent control"
                    ),
                ))

        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for action in actions:
            event_type = "compliance_alert"
            if "contract" in action.action.lower() and "accelerate" in action.action.lower():
                event_type = "contract_velocity_optimization"
            elif "regulatory ontology" in action.action.lower():
                event_type = "regulatory_ontology_update"

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
