"""Head of Patient Experience — L5 Agent #10

Engineer patient experience as versioned causal systems driving retention
and uptake. Tracks touchpoint conversion, LTV delta, NPS-to-retention
causality, and cohort retention curves to emit high-ROI experience
interventions.
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

logger = logging.getLogger("eve.l5.head-patient-experience")

# ---------------------------------------------------------------------------
# Thresholds & constants
# ---------------------------------------------------------------------------

LTV_DELTA_FLOOR = 0.35
CONVERSION_VELOCITY_FLOOR = 0.65
NPS_RETENTION_CAUSALITY_FLOOR = 0.40
CHURN_RATE_CEILING = 0.15
TOUCHPOINT_FAILURE_THRESHOLD = 0.50


class HeadPatientExperienceAgent(L5AgentBase):
    """Detects experience friction and emits journey / touchpoint interventions."""

    role_id: ClassVar[str] = "head-patient-experience"
    display_name: ClassVar[str] = "Head of Patient Experience"
    cadence_seconds: ClassVar[int] = 60
    poll_tables: ClassVar[List[str]] = [
        "ontology_nodes",
        "leads_queue",
        "throughput_ledger",
        "outbox",
    ]

    vanity_metrics: ClassVar[List[str]] = [
        "isolated_nps",
        "isolated_csat",
        "subjective_testimonials",
        "aesthetic_ratings",
        "raw_feedback_volume",
    ]

    signal_metrics: ClassVar[List[str]] = [
        "revenue_attributable_ltv_delta",
        "nps_to_retention_causality",
        "experience_lifted_conversion_velocity",
        "cohort_retention_curves",
        "referral_rate",
        "ab_revenue_impact",
        "churn_reduction_roi",
    ]

    # -- Pipeline stages ----------------------------------------------------

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []

        for row in data.get("ontology_nodes", []):
            attrs = row.get("attributes", {})

            conversion = attrs.get("conversion_velocity")
            if conversion is not None and conversion < CONVERSION_VELOCITY_FLOOR:
                anomalies.append({
                    "type": "conversion_drop",
                    "entity": row.get("entity"),
                    "value": conversion,
                    "threshold": CONVERSION_VELOCITY_FLOOR,
                    "severity": "high" if conversion < CONVERSION_VELOCITY_FLOOR - 0.10 else "medium",
                    "node_id": row.get("node_id"),
                })

            ltv_delta = attrs.get("ltv_delta")
            if ltv_delta is not None and ltv_delta < LTV_DELTA_FLOOR:
                anomalies.append({
                    "type": "experience_friction",
                    "entity": row.get("entity"),
                    "value": ltv_delta,
                    "threshold": LTV_DELTA_FLOOR,
                    "severity": "high",
                    "node_id": row.get("node_id"),
                })

            nps_causality = attrs.get("nps_retention_causality")
            if nps_causality is not None and nps_causality < NPS_RETENTION_CAUSALITY_FLOOR:
                anomalies.append({
                    "type": "nps_revenue_decorrelation",
                    "entity": row.get("entity"),
                    "value": nps_causality,
                    "threshold": NPS_RETENTION_CAUSALITY_FLOOR,
                    "severity": "medium",
                    "node_id": row.get("node_id"),
                })

            touchpoint_success = attrs.get("touchpoint_success_rate")
            if touchpoint_success is not None and touchpoint_success < TOUCHPOINT_FAILURE_THRESHOLD:
                anomalies.append({
                    "type": "touchpoint_failure",
                    "entity": row.get("entity"),
                    "value": touchpoint_success,
                    "threshold": TOUCHPOINT_FAILURE_THRESHOLD,
                    "severity": "high",
                    "node_id": row.get("node_id"),
                })

        for row in data.get("leads_queue", []):
            conv_rate = row.get("conversion_rate")
            if conv_rate is not None and conv_rate < CONVERSION_VELOCITY_FLOOR:
                anomalies.append({
                    "type": "lead_conversion_friction",
                    "entity": row.get("cohort", "unknown"),
                    "value": conv_rate,
                    "threshold": CONVERSION_VELOCITY_FLOOR,
                    "severity": "medium",
                })

        for msg in data.get("_inbox", []):
            if msg.get("event_type") in (
                "growth.lead_signal",
                "talent.performance_update",
                "efficiency.throughput_change",
            ):
                anomalies.append({
                    "type": "cross_agent_experience_signal",
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

            if atype == "conversion_drop":
                gap = CONVERSION_VELOCITY_FLOOR - anomaly["value"]
                roi_lower = gap * 80_000
                roi_upper = gap * 200_000
                actions.append(ActionOutput(
                    action=f"Optimize journey for {anomaly.get('entity', 'unknown')} "
                           f"(conversion={anomaly['value']:.2f}, target={CONVERSION_VELOCITY_FLOOR})",
                    projected_roi=round((roi_lower + roi_upper) / 2, 2),
                    roi_ci=ConfidenceInterval(lower=round(roi_lower, 2), upper=round(roi_upper, 2)),
                    validation_plan="Track conversion velocity weekly for 6 weeks post-intervention; "
                                    "compare cohort vs. control.",
                    kill_criteria="Abort if conversion does not improve >=5pp within 4 weeks.",
                ))

            elif atype == "experience_friction":
                gap = LTV_DELTA_FLOOR - anomaly["value"]
                roi_lower = gap * 100_000
                roi_upper = gap * 300_000
                actions.append(ActionOutput(
                    action=f"Deploy experience intervention for {anomaly.get('entity', 'unknown')} "
                           f"(LTV delta={anomaly['value']:.2f}, target={LTV_DELTA_FLOOR})",
                    projected_roi=round((roi_lower + roi_upper) / 2, 2),
                    roi_ci=ConfidenceInterval(lower=round(roi_lower, 2), upper=round(roi_upper, 2)),
                    validation_plan="Measure LTV delta at 30/60/90 days for treated cohort vs. baseline.",
                    kill_criteria="Abort if LTV delta does not exceed 0.30 within 60 days.",
                ))

            elif atype == "nps_revenue_decorrelation":
                actions.append(ActionOutput(
                    action=f"Recalibrate NPS-to-revenue model for {anomaly.get('entity', 'unknown')} "
                           f"(causality r²={anomaly['value']:.2f}, floor={NPS_RETENTION_CAUSALITY_FLOOR})",
                    projected_roi=15_000.0,
                    roi_ci=ConfidenceInterval(lower=5_000.0, upper=30_000.0),
                    validation_plan="Rebuild causal model with latest 90-day data; validate against holdout.",
                    kill_criteria="Discard model if r² remains < 0.35 after recalibration.",
                ))

            elif atype == "touchpoint_failure":
                actions.append(ActionOutput(
                    action=f"Redesign touchpoint {anomaly.get('entity', 'unknown')} "
                           f"(success rate={anomaly['value']:.2f}, threshold={TOUCHPOINT_FAILURE_THRESHOLD})",
                    projected_roi=20_000.0,
                    roi_ci=ConfidenceInterval(lower=8_000.0, upper=35_000.0),
                    validation_plan="A/B test redesigned touchpoint for 2 weeks; measure conversion lift.",
                    kill_criteria="Abort if A/B test shows no significant lift at p<0.05.",
                ))

            elif atype == "lead_conversion_friction":
                actions.append(ActionOutput(
                    action=f"Design A/B test for lead conversion in cohort {anomaly.get('entity', 'unknown')}",
                    projected_roi=30_000.0,
                    roi_ci=ConfidenceInterval(lower=10_000.0, upper=55_000.0),
                    validation_plan="Run A/B test with minimum 200 leads per variant; revenue as primary endpoint.",
                    kill_criteria="Abort if insufficient sample within 3 weeks.",
                ))

            elif atype == "cross_agent_experience_signal":
                actions.append(ActionOutput(
                    action=f"Evaluate experience impact of {anomaly.get('event_type')} "
                           f"from {anomaly.get('source')}",
                    projected_roi=0.0,
                    roi_ci=ConfidenceInterval(lower=0.0, upper=0.0),
                    validation_plan="Cross-reference with journey ontology; respond within 1 tick.",
                    kill_criteria="Discard if no experience dimension identified.",
                ))

        logger.info("[%s] derived %d actions", self.role_id, len(actions))
        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for action in actions:
            self.publish(
                event_type="experience.action",
                payload=action.model_dump(),
            )

            if "journey" in action.action.lower() or "touchpoint" in action.action.lower():
                self.publish(
                    event_type="experience.journey_patch",
                    payload=action.model_dump(),
                )

            if "a/b" in action.action.lower():
                self.create_task(
                    title=f"[Experience] {action.action[:80]}",
                    description=action.action,
                    priority=2,
                )

            if "churn" in action.action.lower() or "retention" in action.action.lower():
                self.publish(
                    event_type="experience.churn_intervention",
                    payload=action.model_dump(),
                    target="cfo",
                )

        logger.info("[%s] emitted %d actions", self.role_id, len(actions))
