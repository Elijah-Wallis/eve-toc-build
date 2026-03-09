"""Chief Talent Officer — L5 Agent #9

Optimize human systems as a force multiplier for L5 medspa autonomy.
Tracks provider retention cohorts, hiring pipeline velocity, ramp-to-productivity,
and A-player ratio to emit high-ROI talent interventions.
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

logger = logging.getLogger("eve.l5.chief-talent-officer")

# ---------------------------------------------------------------------------
# Thresholds & constants
# ---------------------------------------------------------------------------

RETENTION_FLOOR = 0.92
TIME_TO_PRODUCTIVITY_CEILING_DAYS = 60
A_PLAYER_RATIO_FLOOR = 0.25
PIPELINE_CONVERSION_FLOOR = 0.15
RAMP_VELOCITY_DEGRADATION_PCT = 0.10


class ChiefTalentOfficerAgent(L5AgentBase):
    """Detects talent-system anomalies and emits retention / hiring actions."""

    role_id: ClassVar[str] = "chief-talent-officer"
    display_name: ClassVar[str] = "Chief Talent Officer"
    cadence_seconds: ClassVar[int] = 60
    poll_tables: ClassVar[List[str]] = [
        "ontology_nodes",
        "tasks",
        "heartbeats",
        "outbox",
    ]

    vanity_metrics: ClassVar[List[str]] = [
        "gross_headcount",
        "total_applications_received",
        "average_tenure",
        "training_hours_logged",
        "subjective_culture_fit",
        "engagement_scores",
        "pedigree",
        "years_of_experience",
        "degrees",
        "linkedin_network_size",
    ]

    signal_metrics: ClassVar[List[str]] = [
        "provider_retention_by_cohort",
        "time_to_productivity",
        "output_per_provider",
        "employee_referral_to_hire_rate",
        "90_day_survival_rate",
        "a_player_ratio",
        "cost_of_bad_hire",
    ]

    # -- Pipeline stages ----------------------------------------------------

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []

        for row in data.get("ontology_nodes", []):
            attrs = row.get("attributes", {})

            retention = attrs.get("retention_rate")
            if retention is not None and retention < RETENTION_FLOOR:
                anomalies.append({
                    "type": "retention_drop",
                    "entity": row.get("entity"),
                    "value": retention,
                    "threshold": RETENTION_FLOOR,
                    "severity": "high" if retention < RETENTION_FLOOR - 0.05 else "medium",
                    "node_id": row.get("node_id"),
                })

            ttp = attrs.get("time_to_productivity_days")
            if ttp is not None and ttp > TIME_TO_PRODUCTIVITY_CEILING_DAYS:
                anomalies.append({
                    "type": "ramp_velocity_degradation",
                    "entity": row.get("entity"),
                    "value": ttp,
                    "threshold": TIME_TO_PRODUCTIVITY_CEILING_DAYS,
                    "severity": "medium",
                    "node_id": row.get("node_id"),
                })

            a_ratio = attrs.get("a_player_ratio")
            if a_ratio is not None and a_ratio < A_PLAYER_RATIO_FLOOR:
                anomalies.append({
                    "type": "a_player_ratio_drift",
                    "entity": row.get("entity"),
                    "value": a_ratio,
                    "threshold": A_PLAYER_RATIO_FLOOR,
                    "severity": "high",
                    "node_id": row.get("node_id"),
                })

            pipeline_conv = attrs.get("pipeline_conversion_rate")
            if pipeline_conv is not None and pipeline_conv < PIPELINE_CONVERSION_FLOOR:
                anomalies.append({
                    "type": "hiring_pipeline_bottleneck",
                    "entity": row.get("entity"),
                    "value": pipeline_conv,
                    "threshold": PIPELINE_CONVERSION_FLOOR,
                    "severity": "medium",
                    "node_id": row.get("node_id"),
                })

        for msg in data.get("_inbox", []):
            if msg.get("event_type") in (
                "efficiency.constraint_report",
                "growth.capacity_request",
            ):
                anomalies.append({
                    "type": "cross_agent_talent_signal",
                    "source": msg.get("source_agent"),
                    "event_type": msg.get("event_type"),
                    "payload": msg.get("payload", {}),
                    "severity": "medium",
                })

        logger.info("[%s] detected %d anomalies", self.role_id, len(anomalies))
        return anomalies

    def derive_intelligence(
        self, anomalies: List[Dict], data: Dict[str, List[Dict]]
    ) -> List[ActionOutput]:
        actions: List[ActionOutput] = []

        for anomaly in anomalies:
            atype = anomaly.get("type")

            if atype == "retention_drop":
                gap = RETENTION_FLOOR - anomaly["value"]
                roi_lower = gap * 50_000
                roi_upper = gap * 120_000
                actions.append(ActionOutput(
                    action=f"Initiate retention intervention for {anomaly.get('entity', 'unknown')} "
                           f"(retention={anomaly['value']:.2f}, target={RETENTION_FLOOR})",
                    projected_roi=round((roi_lower + roi_upper) / 2, 2),
                    roi_ci=ConfidenceInterval(lower=round(roi_lower, 2), upper=round(roi_upper, 2)),
                    validation_plan="Track cohort retention weekly for 8 weeks post-intervention; "
                                    "compare to pre-intervention baseline.",
                    kill_criteria="Abort if retention does not improve by >=2pp within 6 weeks.",
                ))

            elif atype == "ramp_velocity_degradation":
                days_over = anomaly["value"] - TIME_TO_PRODUCTIVITY_CEILING_DAYS
                actions.append(ActionOutput(
                    action=f"Accelerate onboarding for {anomaly.get('entity', 'unknown')} "
                           f"(ramp={anomaly['value']}d, ceiling={TIME_TO_PRODUCTIVITY_CEILING_DAYS}d)",
                    projected_roi=round(days_over * 800, 2),
                    roi_ci=ConfidenceInterval(lower=round(days_over * 400, 2), upper=round(days_over * 1200, 2)),
                    validation_plan="Measure next-cohort time-to-90%-output against current baseline.",
                    kill_criteria="Abort if next cohort ramp is not >=10% faster within 90 days.",
                ))

            elif atype == "hiring_pipeline_bottleneck":
                actions.append(ActionOutput(
                    action=f"Optimize hiring pipeline for {anomaly.get('entity', 'unknown')} "
                           f"(conversion={anomaly['value']:.2f}, floor={PIPELINE_CONVERSION_FLOOR})",
                    projected_roi=25_000.0,
                    roi_ci=ConfidenceInterval(lower=10_000.0, upper=45_000.0),
                    validation_plan="Track pipeline conversion rate bi-weekly; target >{PIPELINE_CONVERSION_FLOOR}.",
                    kill_criteria="Abort if conversion does not reach floor within 4 weeks.",
                ))

            elif atype == "a_player_ratio_drift":
                actions.append(ActionOutput(
                    action=f"Performance loop adjustment: raise A-player ratio "
                           f"(current={anomaly['value']:.2f}, floor={A_PLAYER_RATIO_FLOOR})",
                    projected_roi=40_000.0,
                    roi_ci=ConfidenceInterval(lower=15_000.0, upper=70_000.0),
                    validation_plan="Quarterly A-player ratio measurement vs. baseline.",
                    kill_criteria="Abort if ratio does not improve within 2 quarters.",
                ))

            elif atype == "cross_agent_talent_signal":
                actions.append(ActionOutput(
                    action=f"Evaluate talent dimension of {anomaly.get('event_type')} "
                           f"from {anomaly.get('source')}",
                    projected_roi=0.0,
                    roi_ci=ConfidenceInterval(lower=0.0, upper=0.0),
                    validation_plan="Cross-reference with talent ontology; respond within 1 tick.",
                    kill_criteria="Discard if talent is not the binding constraint.",
                ))

        logger.info("[%s] derived %d actions", self.role_id, len(actions))
        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for action in actions:
            self.publish(
                event_type="talent.action",
                payload=action.model_dump(),
            )

            if "retention" in action.action.lower():
                self.publish(
                    event_type="talent.retention_alert",
                    payload=action.model_dump(),
                    target="cfo",
                )

            if "hiring" in action.action.lower() or "pipeline" in action.action.lower():
                self.create_task(
                    title=f"[Talent] {action.action[:80]}",
                    description=action.action,
                    priority=2,
                )
                self.publish(
                    event_type="talent.hiring_trigger",
                    payload=action.model_dump(),
                    target="head-growth",
                )

        logger.info("[%s] emitted %d actions", self.role_id, len(actions))
