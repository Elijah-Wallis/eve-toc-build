"""
Head of Scale and Hive Mind — L5 Agent Core
=============================================
Architects and executes synchronized multi-site scaling and real-time
Hive Mind intelligence fusion across all agents.
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

logger = logging.getLogger("eve.l5.head-scale-hive-mind")


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class SitePerformance(BaseModel):
    site_id: str
    fcf_yield: float = 0.0
    ramp_days: int = 0
    replication_fidelity: float = 1.0
    capital_efficiency: float = 0.0
    stage: str = "pre-launch"


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

FIDELITY_FLOOR = 0.85
RAMP_VELOCITY_TARGET_DAYS = 180
RAMP_VELOCITY_OVERSHOOT = 1.3
CAPITAL_EFFICIENCY_MIN = 1.5
HIVE_PROPAGATION_SLA_HOURS = 48
PORTFOLIO_CONCENTRATION_LIMIT = 0.15


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class HeadScaleHiveMindAgent(L5AgentBase):

    role_id: ClassVar[str] = "head-scale-hive-mind"
    display_name: ClassVar[str] = "Head of Scale and Hive Mind"
    cadence_seconds: ClassVar[int] = 120
    poll_tables: ClassVar[List[str]] = [
        "ontology_nodes",
        "tasks",
        "heartbeats",
        "outbox",
    ]

    vanity_metrics: ClassVar[List[str]] = [
        "Gross location count",
        "Aggregate portfolio revenue",
        "Headcount growth",
        "Market share %",
        "Announced expansion timelines",
    ]

    signal_metrics: ClassVar[List[str]] = [
        "Per-location FCF yield",
        "Portfolio IRR consistency",
        "FCF CAGR",
        "New-site ramp velocity",
        "Hive knowledge transfer velocity",
        "Expansion capital efficiency ratio",
        "Replication fidelity score",
    ]

    # -- Pipeline stages ----------------------------------------------------

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []

        for node in data.get("ontology_nodes", []):
            attrs = node.get("attributes", {})

            fidelity = attrs.get("replication_fidelity")
            if fidelity is not None and fidelity < FIDELITY_FLOOR:
                anomalies.append({
                    "type": "replication_fidelity_drop",
                    "entity": node.get("entity"),
                    "site_id": attrs.get("site_id"),
                    "value": fidelity,
                    "threshold": FIDELITY_FLOOR,
                    "node": node,
                })

            ramp = attrs.get("ramp_days")
            if ramp is not None and ramp > RAMP_VELOCITY_TARGET_DAYS * RAMP_VELOCITY_OVERSHOOT:
                anomalies.append({
                    "type": "ramp_velocity_anomaly",
                    "entity": node.get("entity"),
                    "site_id": attrs.get("site_id"),
                    "value": ramp,
                    "threshold": RAMP_VELOCITY_TARGET_DAYS * RAMP_VELOCITY_OVERSHOOT,
                    "node": node,
                })

            cap_eff = attrs.get("capital_efficiency")
            if cap_eff is not None and 0 < cap_eff < CAPITAL_EFFICIENCY_MIN:
                anomalies.append({
                    "type": "capital_efficiency_degradation",
                    "entity": node.get("entity"),
                    "site_id": attrs.get("site_id"),
                    "value": cap_eff,
                    "threshold": CAPITAL_EFFICIENCY_MIN,
                    "node": node,
                })

            fcf_share = attrs.get("portfolio_fcf_share")
            if fcf_share is not None and fcf_share > PORTFOLIO_CONCENTRATION_LIMIT:
                anomalies.append({
                    "type": "portfolio_concentration_breach",
                    "entity": node.get("entity"),
                    "site_id": attrs.get("site_id"),
                    "value": fcf_share,
                    "threshold": PORTFOLIO_CONCENTRATION_LIMIT,
                    "node": node,
                })

        for hb in data.get("heartbeats", []):
            if hb.get("status") != "alive":
                anomalies.append({
                    "type": "hive_propagation_latency",
                    "agent_id": hb.get("agent_id"),
                    "status": hb.get("status"),
                })

        for msg in data.get("_inbox", []):
            if msg.get("event_type") == "financial_update":
                payload = msg.get("payload", {})
                site_fcf = payload.get("fcf_yield", 0)
                if site_fcf < 0:
                    anomalies.append({
                        "type": "unit_economics_deviation",
                        "source_agent": msg.get("source_agent"),
                        "site_id": payload.get("site_id"),
                        "fcf_yield": site_fcf,
                    })

        logger.info("[%s] detected %d anomalies", self.role_id, len(anomalies))
        return anomalies

    def derive_intelligence(
        self, anomalies: List[Dict], data: Dict[str, List[Dict]]
    ) -> List[ActionOutput]:
        actions: List[ActionOutput] = []

        for anomaly in anomalies:
            atype = anomaly.get("type", "")

            if atype == "replication_fidelity_drop":
                actions.append(ActionOutput(
                    action=f"Corrective replication protocol for site "
                           f"{anomaly.get('site_id')} "
                           f"(fidelity={anomaly.get('value'):.2f})",
                    projected_roi=2.0,
                    roi_ci=ConfidenceInterval(lower=1.0, upper=3.5),
                    validation_plan="Monitor fidelity score for 14 days; "
                                    "target recovery above 0.90",
                    kill_criteria="Fidelity does not recover above 0.85 within 30 days",
                ))

            elif atype == "ramp_velocity_anomaly":
                actions.append(ActionOutput(
                    action=f"Investigate ramp delay at site {anomaly.get('site_id')} "
                           f"({anomaly.get('value')} days vs {RAMP_VELOCITY_TARGET_DAYS}d target)",
                    projected_roi=1.5,
                    roi_ci=ConfidenceInterval(lower=0.5, upper=3.0),
                    validation_plan="Root-cause analysis within 7 days; "
                                    "implement corrective actions and re-measure in 30 days",
                    kill_criteria="Site cannot project breakeven within 2× target ramp period",
                ))

            elif atype == "capital_efficiency_degradation":
                actions.append(ActionOutput(
                    action=f"Capital efficiency audit for site {anomaly.get('site_id')} "
                           f"(ratio={anomaly.get('value'):.2f} vs {CAPITAL_EFFICIENCY_MIN} min)",
                    projected_roi=2.5,
                    roi_ci=ConfidenceInterval(lower=1.2, upper=4.5),
                    validation_plan="Cost audit within 14 days; "
                                    "verify efficiency improvement to ≥1.5×",
                    kill_criteria="Capital efficiency remains below 1.5× after 60 days",
                ))

            elif atype == "portfolio_concentration_breach":
                actions.append(ActionOutput(
                    action=f"Rebalance portfolio: site {anomaly.get('site_id')} "
                           f"represents {anomaly.get('value'):.0%} of FCF "
                           f"(limit={PORTFOLIO_CONCENTRATION_LIMIT:.0%})",
                    projected_roi=1.8,
                    roi_ci=ConfidenceInterval(lower=0.8, upper=3.2),
                    validation_plan="Accelerate ramp at other sites; "
                                    "verify concentration drops below 15% in 90 days",
                    kill_criteria="Concentration unchanged after 90 days despite intervention",
                ))

            elif atype == "hive_propagation_latency":
                actions.append(ActionOutput(
                    action=f"Accelerate hive sync for agent {anomaly.get('agent_id')} "
                           f"(status={anomaly.get('status')})",
                    projected_roi=1.2,
                    roi_ci=ConfidenceInterval(lower=0.5, upper=2.0),
                    validation_plan="Verify agent returns to alive status within 4h; "
                                    "confirm playbook sync completes",
                    kill_criteria="Agent remains unreachable after 24h",
                ))

            elif atype == "unit_economics_deviation":
                actions.append(ActionOutput(
                    action=f"Halt expansion planning for site {anomaly.get('site_id')}: "
                           f"negative FCF yield ({anomaly.get('fcf_yield'):.2f})",
                    projected_roi=3.0,
                    roi_ci=ConfidenceInterval(lower=1.5, upper=5.0),
                    validation_plan="Coordinate with Head of Unit Economics for root cause; "
                                    "resume only after positive FCF projection validated",
                    kill_criteria="Site cannot project positive FCF within 90 days",
                ))

        logger.info("[%s] derived %d actions", self.role_id, len(actions))
        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for action in actions:
            self.publish(
                event_type="scaling_event",
                payload=action.model_dump(),
            )

            if "halt expansion" in action.action.lower():
                self.create_task(
                    title=f"Expansion halt: {action.action[:80]}",
                    description=action.action,
                    priority=1,
                )
            elif "corrective" in action.action.lower():
                self.create_task(
                    title=f"Replication correction: {action.action[:80]}",
                    description=action.action,
                    priority=2,
                )
            elif "audit" in action.action.lower():
                self.create_task(
                    title=f"Scaling audit: {action.action[:80]}",
                    description=action.action,
                    priority=2,
                    assigned_to="head-unit-economics",
                )

            self._update_scaling_ontology_node(action)

        logger.info("[%s] emitted %d actions", self.role_id, len(actions))

    # -- Helpers ------------------------------------------------------------

    def _update_scaling_ontology_node(self, action: ActionOutput) -> None:
        node = OntologyNode(
            entity="scaling_action",
            attributes={
                "action": action.action,
                "projected_roi": action.projected_roi,
                "source_agent": self.role_id,
            },
            causal_relations=[{
                "target": "portfolio_outcome",
                "relation": "improves_irr",
                "weight": action.projected_roi / 10.0,
                "confidence": action.roi_ci.confidence,
            }],
            quantitative_thresholds={
                "fidelity_floor": FIDELITY_FLOOR,
                "ramp_target_days": float(RAMP_VELOCITY_TARGET_DAYS),
                "capital_efficiency_min": CAPITAL_EFFICIENCY_MIN,
            },
            statistical_confidence=action.roi_ci.confidence,
            self_correction_triggers=[action.kill_criteria],
            derivative_intelligence_hooks=[
                "portfolio_irr_recalc",
                "replication_protocol_update",
            ],
            roi_projection_link=action.action[:64],
        )
        self.upsert_ontology_node(node)
