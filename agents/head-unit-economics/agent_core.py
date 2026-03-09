"""
Head of Unit Economics — L5 Agent Core
=======================================
Enforces unit economics truth. Optimizes for contribution margin per unit,
LTV:CAC, payback periods, cohort profitability, and marginal ROI.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel, Field

from agents.l5.base import (
    ActionOutput,
    ConfidenceInterval,
    L5AgentBase,
    OntologyNode,
    OutboxMessage,
)

logger = logging.getLogger("eve.l5.head-unit-economics")


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class ChannelMetrics(BaseModel):
    channel_id: str
    ltv_cac_ratio: float = 0.0
    payback_months: float = 0.0
    contribution_margin: float = 0.0
    marginal_roi: float = 0.0
    status: str = "active"


class CohortMetrics(BaseModel):
    cohort_id: str
    lifetime_profit: float = 0.0
    repeat_revenue_rate: float = 0.0
    payback_months: float = 0.0


# ---------------------------------------------------------------------------
# Thresholds — corrective loops
# ---------------------------------------------------------------------------

LTV_CAC_FLOOR = 2.5
LTV_CAC_TARGET = 3.0
PAYBACK_TARGET_MONTHS = 5.0
PAYBACK_CEILING_MONTHS = 6.0
CONTRIBUTION_MARGIN_FLOOR = 0.40
CONTRIBUTION_MARGIN_SHUTDOWN = 0.25
COHORT_NEGATIVE_MAX_PERIODS = 2


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class HeadUnitEconomicsAgent(L5AgentBase):

    role_id: ClassVar[str] = "head-unit-economics"
    display_name: ClassVar[str] = "Head of Unit Economics"
    cadence_seconds: ClassVar[int] = 60
    poll_tables: ClassVar[List[str]] = [
        "throughput_ledger",
        "leads_queue",
        "ontology_nodes",
        "outbox",
    ]

    vanity_metrics: ClassVar[List[str]] = [
        "Gross Revenue",
        "Total Patient Volume",
        "Growth Rate",
        "Average Ticket Size",
        "Gross Margin %",
        "Market Share",
    ]

    signal_metrics: ClassVar[List[str]] = [
        "LTV:CAC Ratio",
        "Payback Period",
        "Contribution Margin per Treatment",
        "Cohort Lifetime Profit",
        "Channel-Specific Marginal ROI",
        "Repeat Revenue Rate",
        "Break-even Volume per Channel",
    ]

    # -- Pipeline stages ----------------------------------------------------

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []

        for row in data.get("throughput_ledger", []):
            ltv_cac = row.get("ltv_cac_ratio")
            if ltv_cac is not None and ltv_cac < LTV_CAC_FLOOR:
                anomalies.append({
                    "type": "ltv_cac_degradation",
                    "channel": row.get("channel_id", "unknown"),
                    "value": ltv_cac,
                    "threshold": LTV_CAC_FLOOR,
                    "row": row,
                })

            margin = row.get("contribution_margin")
            if margin is not None and margin < CONTRIBUTION_MARGIN_FLOOR:
                anomalies.append({
                    "type": "margin_compression",
                    "channel": row.get("channel_id", "unknown"),
                    "value": margin,
                    "threshold": CONTRIBUTION_MARGIN_FLOOR,
                    "shutdown": margin < CONTRIBUTION_MARGIN_SHUTDOWN,
                    "row": row,
                })

        for row in data.get("leads_queue", []):
            payback = row.get("payback_months")
            if payback is not None and payback > PAYBACK_CEILING_MONTHS:
                anomalies.append({
                    "type": "payback_elongation",
                    "channel": row.get("channel_id", "unknown"),
                    "cohort": row.get("cohort_id", "unknown"),
                    "value": payback,
                    "threshold": PAYBACK_CEILING_MONTHS,
                    "row": row,
                })

        for node in data.get("ontology_nodes", []):
            attrs = node.get("attributes", {})

            lifetime_profit = attrs.get("lifetime_profit")
            if lifetime_profit is not None and lifetime_profit < 0:
                neg_periods = attrs.get("negative_periods", 1)
                if neg_periods >= COHORT_NEGATIVE_MAX_PERIODS:
                    anomalies.append({
                        "type": "cohort_profitability_drop",
                        "cohort": attrs.get("cohort_id", node.get("entity")),
                        "value": lifetime_profit,
                        "negative_periods": neg_periods,
                        "node": node,
                    })

            marginal_roi = attrs.get("marginal_roi")
            if marginal_roi is not None and marginal_roi < 0:
                anomalies.append({
                    "type": "negative_marginal_roi",
                    "channel": attrs.get("channel_id", node.get("entity")),
                    "value": marginal_roi,
                    "node": node,
                })

        for msg in data.get("_inbox", []):
            if msg.get("event_type") == "scaling_event":
                payload = msg.get("payload", {})
                if "expansion" in payload.get("action", "").lower():
                    anomalies.append({
                        "type": "growth_proposal_validation_needed",
                        "source_agent": msg.get("source_agent"),
                        "payload": payload,
                    })

        logger.info("[%s] detected %d anomalies", self.role_id, len(anomalies))
        return anomalies

    def derive_intelligence(
        self, anomalies: List[Dict], data: Dict[str, List[Dict]]
    ) -> List[ActionOutput]:
        actions: List[ActionOutput] = []

        for anomaly in anomalies:
            atype = anomaly.get("type", "")

            if atype == "ltv_cac_degradation":
                actions.append(ActionOutput(
                    action=f"Acquisition pause on channel {anomaly.get('channel')}: "
                           f"LTV:CAC={anomaly.get('value'):.2f} "
                           f"(floor={LTV_CAC_FLOOR})",
                    projected_roi=3.0,
                    roi_ci=ConfidenceInterval(lower=1.5, upper=5.0),
                    validation_plan="Monitor LTV:CAC recovery over 30 days after pause; "
                                    "resume only when ratio exceeds 2.5",
                    kill_criteria="LTV:CAC does not recover above 2.5 within 60 days; "
                                  "consider permanent channel shutdown",
                ))

            elif atype == "payback_elongation":
                actions.append(ActionOutput(
                    action=f"Channel/offer redesign for {anomaly.get('channel')} "
                           f"(cohort {anomaly.get('cohort')}): "
                           f"payback={anomaly.get('value'):.1f}mo "
                           f"(ceiling={PAYBACK_CEILING_MONTHS}mo)",
                    projected_roi=2.5,
                    roi_ci=ConfidenceInterval(lower=1.0, upper=4.5),
                    validation_plan="A/B test redesigned offer within 14 days; "
                                    "measure payback reduction in next cohort",
                    kill_criteria="Payback remains above 6 months after 2 redesign cycles",
                ))

            elif atype == "margin_compression":
                if anomaly.get("shutdown"):
                    actions.append(ActionOutput(
                        action=f"Channel shutdown for {anomaly.get('channel')}: "
                               f"margin={anomaly.get('value'):.0%} "
                               f"(below shutdown threshold {CONTRIBUTION_MARGIN_SHUTDOWN:.0%})",
                        projected_roi=4.0,
                        roi_ci=ConfidenceInterval(lower=2.0, upper=7.0),
                        validation_plan="Confirm channel fully wound down within 7 days; "
                                        "reallocate budget to highest-marginal-ROI channels",
                        kill_criteria="N/A — channel is permanently shut down",
                    ))
                else:
                    actions.append(ActionOutput(
                        action=f"Cost audit for channel {anomaly.get('channel')}: "
                               f"margin={anomaly.get('value'):.0%} "
                               f"(floor={CONTRIBUTION_MARGIN_FLOOR:.0%})",
                        projected_roi=2.0,
                        roi_ci=ConfidenceInterval(lower=0.8, upper=3.5),
                        validation_plan="Complete cost audit within 14 days; "
                                        "identify and eliminate cost drivers; "
                                        "verify margin recovery above 40%",
                        kill_criteria="Margin does not recover above 40% within 45 days; "
                                      "escalate to channel shutdown",
                    ))

            elif atype == "cohort_profitability_drop":
                actions.append(ActionOutput(
                    action=f"Investigate negative cohort profitability for "
                           f"{anomaly.get('cohort')} "
                           f"(profit={anomaly.get('value'):.0f}, "
                           f"negative for {anomaly.get('negative_periods')} periods)",
                    projected_roi=3.5,
                    roi_ci=ConfidenceInterval(lower=1.5, upper=6.0),
                    validation_plan="Root-cause analysis within 7 days; "
                                    "implement corrective pricing/cost actions; "
                                    "verify cohort returns to positive within 30 days",
                    kill_criteria="Cohort remains unprofitable after 3 consecutive periods; "
                                  "discontinue cohort acquisition",
                ))

            elif atype == "negative_marginal_roi":
                actions.append(ActionOutput(
                    action=f"Deprioritize channel {anomaly.get('channel')}: "
                           f"negative marginal ROI ({anomaly.get('value'):.2f})",
                    projected_roi=2.0,
                    roi_ci=ConfidenceInterval(lower=1.0, upper=3.5),
                    validation_plan="Reduce spend incrementally over 14 days; "
                                    "measure marginal ROI improvement",
                    kill_criteria="Marginal ROI remains negative after spend reduction; "
                                  "shut down channel",
                ))

            elif atype == "growth_proposal_validation_needed":
                validated = self._validate_growth_proposal(anomaly.get("payload", {}))
                event = "unit_economics_validated" if validated else "acquisition_pause"
                actions.append(ActionOutput(
                    action=f"Growth proposal {'approved' if validated else 'rejected'} "
                           f"from {anomaly.get('source_agent')}: "
                           f"unit economics {'pass' if validated else 'fail'}",
                    projected_roi=1.0 if validated else 0.0,
                    roi_ci=ConfidenceInterval(
                        lower=0.5 if validated else -1.0,
                        upper=2.0 if validated else 0.5,
                    ),
                    validation_plan="Monitor post-expansion unit economics for 90 days"
                                    if validated else
                                    "Proposal must be revised to meet unit economics gates",
                    kill_criteria="Post-expansion LTV:CAC drops below 2.5 or "
                                  "payback exceeds 6 months",
                ))

        logger.info("[%s] derived %d actions", self.role_id, len(actions))
        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for action in actions:
            event_type = "financial_update"
            if "pause" in action.action.lower():
                event_type = "acquisition_pause"
            elif "validated" in action.action.lower() or "approved" in action.action.lower():
                event_type = "unit_economics_validated"
            elif "margin" in action.action.lower() or "audit" in action.action.lower():
                event_type = "margin_alert"

            self.publish(event_type=event_type, payload=action.model_dump())

            if "pause" in action.action.lower() or "shutdown" in action.action.lower():
                self.create_task(
                    title=f"Acquisition action: {action.action[:80]}",
                    description=action.action,
                    priority=1,
                )
            elif "audit" in action.action.lower():
                self.create_task(
                    title=f"Cost audit: {action.action[:80]}",
                    description=action.action,
                    priority=2,
                )
            elif "redesign" in action.action.lower():
                self.create_task(
                    title=f"Channel redesign: {action.action[:80]}",
                    description=action.action,
                    priority=2,
                )

            self._update_unit_economics_ontology_node(action)

        logger.info("[%s] emitted %d actions", self.role_id, len(actions))

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _validate_growth_proposal(payload: Dict) -> bool:
        projected_ltv_cac = payload.get("projected_ltv_cac", 0)
        projected_payback = payload.get("projected_payback_months", 99)
        projected_margin = payload.get("projected_contribution_margin", 0)
        return (
            projected_ltv_cac >= LTV_CAC_FLOOR
            and projected_payback <= PAYBACK_CEILING_MONTHS
            and projected_margin >= CONTRIBUTION_MARGIN_FLOOR
        )

    def _update_unit_economics_ontology_node(self, action: ActionOutput) -> None:
        node = OntologyNode(
            entity="unit_economics_action",
            attributes={
                "action": action.action,
                "projected_roi": action.projected_roi,
                "source_agent": self.role_id,
            },
            causal_relations=[{
                "target": "fcf_outcome",
                "relation": "improves_margin",
                "weight": action.projected_roi / 10.0,
                "confidence": action.roi_ci.confidence,
            }],
            quantitative_thresholds={
                "ltv_cac_floor": LTV_CAC_FLOOR,
                "payback_ceiling_months": PAYBACK_CEILING_MONTHS,
                "contribution_margin_floor": CONTRIBUTION_MARGIN_FLOOR,
            },
            statistical_confidence=action.roi_ci.confidence,
            self_correction_triggers=[action.kill_criteria],
            derivative_intelligence_hooks=[
                "marginal_roi_recalc",
                "cohort_ltv_update",
                "channel_efficiency_rerank",
            ],
            roi_projection_link=action.action[:64],
        )
        self.upsert_ontology_node(node)
