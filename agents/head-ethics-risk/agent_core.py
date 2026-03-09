"""
Head of Ethics and Risk — L5 Agent Core
========================================
Quantifies every risk and ethical vector using Bayesian P×I×V×contagion
ontology with real-time data from all 15 peer agents.
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

logger = logging.getLogger("eve.l5.head-ethics-risk")


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class RiskScore(BaseModel):
    """Composite risk score: P × Impact × Velocity × (1 + Interdependency) × Truth_Deviation."""

    entity_id: str
    probability: float = Field(ge=0.0, le=1.0)
    impact: float = Field(ge=0.0)
    velocity: float = Field(ge=0.0)
    interdependency: float = Field(ge=0.0)
    truth_deviation: float = Field(ge=0.0, le=1.0)

    @property
    def composite(self) -> float:
        return (
            self.probability
            * self.impact
            * self.velocity
            * (1 + self.interdependency)
            * self.truth_deviation
        )


class EthicsAudit(BaseModel):
    entity_id: str
    integrity_score: float = Field(ge=0.0, le=1.0)
    truth_seeking: bool = True
    non_deception: bool = True
    patient_consent: bool = True
    harm_minimization: bool = True
    findings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

REV_ALERT_THRESHOLD = 50_000.0
CVAR_99_9_THRESHOLD = 250_000.0
ETHICS_INTEGRITY_FLOOR = 0.7
CONTAGION_CIRCUIT_BREAKER = 0.8
TRUTH_DEVIATION_CEILING = 0.3


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class HeadEthicsRiskAgent(L5AgentBase):

    role_id: ClassVar[str] = "head-ethics-risk"
    display_name: ClassVar[str] = "Head of Ethics and Risk"
    cadence_seconds: ClassVar[int] = 60
    poll_tables: ClassVar[List[str]] = [
        "ontology_nodes",
        "tasks",
        "heartbeats",
        "outbox",
    ]

    vanity_metrics: ClassVar[List[str]] = [
        "Compliance checkboxes",
        "Policy volume",
        "Subjective ethics feel",
        "Regulatory theater",
        "PR signaling",
        "Zero-risk paralysis",
        "Performative virtue",
    ]

    signal_metrics: ClassVar[List[str]] = [
        "Risk Exposure Value (REV)",
        "Mitigation ROI",
        "Tail-risk Expected Shortfall (99.9% CVaR)",
        "Ethics Integrity Bayesian Score",
        "Risk-Adjusted Scaling Multiplier",
        "Breach Probability Reduction",
        "Decision Truth Update Rate",
        "Systemic Contagion Factor",
    ]

    # -- Pipeline stages ----------------------------------------------------

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []

        for node in data.get("ontology_nodes", []):
            attrs = node.get("attributes", {})

            rev = attrs.get("rev")
            if rev is not None and rev > REV_ALERT_THRESHOLD:
                anomalies.append({
                    "type": "risk_exposure_spike",
                    "entity": node.get("entity"),
                    "value": rev,
                    "threshold": REV_ALERT_THRESHOLD,
                    "node": node,
                })

            cvar = attrs.get("cvar_99_9")
            if cvar is not None and cvar > CVAR_99_9_THRESHOLD:
                anomalies.append({
                    "type": "tail_risk_breach",
                    "entity": node.get("entity"),
                    "value": cvar,
                    "threshold": CVAR_99_9_THRESHOLD,
                    "node": node,
                })

            ethics = attrs.get("ethics_integrity")
            if ethics is not None and ethics < ETHICS_INTEGRITY_FLOOR:
                anomalies.append({
                    "type": "ethics_integrity_drop",
                    "entity": node.get("entity"),
                    "value": ethics,
                    "threshold": ETHICS_INTEGRITY_FLOOR,
                    "node": node,
                })

            contagion = attrs.get("contagion_factor")
            if contagion is not None and contagion > CONTAGION_CIRCUIT_BREAKER:
                anomalies.append({
                    "type": "contagion_vector",
                    "entity": node.get("entity"),
                    "value": contagion,
                    "threshold": CONTAGION_CIRCUIT_BREAKER,
                    "node": node,
                })

            td = attrs.get("truth_deviation")
            if td is not None and td > TRUTH_DEVIATION_CEILING:
                anomalies.append({
                    "type": "truth_deviation_ceiling_breach",
                    "entity": node.get("entity"),
                    "value": td,
                    "threshold": TRUTH_DEVIATION_CEILING,
                    "node": node,
                })

        for msg in data.get("_inbox", []):
            if msg.get("event_type") == "anomaly_detected":
                anomalies.append({
                    "type": "peer_anomaly",
                    "source_agent": msg.get("source_agent"),
                    "payload": msg.get("payload", {}),
                })

        logger.info("[%s] detected %d anomalies", self.role_id, len(anomalies))
        return anomalies

    def derive_intelligence(
        self, anomalies: List[Dict], data: Dict[str, List[Dict]]
    ) -> List[ActionOutput]:
        actions: List[ActionOutput] = []

        for anomaly in anomalies:
            atype = anomaly.get("type", "")

            if atype == "risk_exposure_spike":
                actions.append(ActionOutput(
                    action=f"Deploy mitigation for REV spike on {anomaly.get('entity')} "
                           f"(value={anomaly.get('value'):.0f})",
                    projected_roi=2.5,
                    roi_ci=ConfidenceInterval(lower=1.2, upper=4.0),
                    validation_plan="Monitor REV for 24h post-mitigation; "
                                    "confirm drop below threshold",
                    kill_criteria="REV does not decrease within 48h or new exposure emerges",
                ))

            elif atype == "tail_risk_breach":
                actions.append(ActionOutput(
                    action=f"Activate tail-risk containment for {anomaly.get('entity')} "
                           f"(CVaR={anomaly.get('value'):.0f})",
                    projected_roi=5.0,
                    roi_ci=ConfidenceInterval(lower=2.0, upper=10.0),
                    validation_plan="Run Monte Carlo simulation post-containment; "
                                    "verify CVaR below 2× acceptable",
                    kill_criteria="CVaR remains above threshold after 72h containment",
                ))

            elif atype == "ethics_integrity_drop":
                actions.append(ActionOutput(
                    action=f"Trigger ethics audit for {anomaly.get('entity')} "
                           f"(integrity={anomaly.get('value'):.2f})",
                    projected_roi=1.8,
                    roi_ci=ConfidenceInterval(lower=0.8, upper=3.0),
                    validation_plan="Complete audit within 24h; verify score recovery "
                                    "above floor post-remediation",
                    kill_criteria="Audit reveals systemic issue requiring full process halt",
                ))

            elif atype == "contagion_vector":
                actions.append(ActionOutput(
                    action=f"Initiate contagion containment protocol for "
                           f"{anomaly.get('entity')} (factor={anomaly.get('value'):.2f})",
                    projected_roi=4.0,
                    roi_ci=ConfidenceInterval(lower=1.5, upper=8.0),
                    validation_plan="Monitor contagion factor across all connected nodes "
                                    "for 48h; confirm decay below 0.5",
                    kill_criteria="Contagion continues to propagate after 48h containment",
                ))

            elif atype == "truth_deviation_ceiling_breach":
                actions.append(ActionOutput(
                    action=f"Escalate truth deviation for {anomaly.get('entity')} "
                           f"(deviation={anomaly.get('value'):.2f}); halt affected processes",
                    projected_roi=3.0,
                    roi_ci=ConfidenceInterval(lower=1.0, upper=6.0),
                    validation_plan="Verify truth alignment restored within 24h "
                                    "via independent data cross-check",
                    kill_criteria="Truth deviation persists above 0.3 after remediation",
                ))

            elif atype == "peer_anomaly":
                score = self._compute_risk_score_for_peer_anomaly(anomaly)
                if score > REV_ALERT_THRESHOLD:
                    actions.append(ActionOutput(
                        action=f"Cross-domain risk correlation: peer anomaly from "
                               f"{anomaly.get('source_agent')} requires mitigation "
                               f"(computed REV={score:.0f})",
                        projected_roi=2.0,
                        roi_ci=ConfidenceInterval(lower=0.5, upper=4.0),
                        validation_plan="Validate cross-domain impact within 24h; "
                                        "update Bayesian posteriors",
                        kill_criteria="Cross-domain impact assessment is negligible",
                    ))

        logger.info("[%s] derived %d actions", self.role_id, len(actions))
        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for action in actions:
            self.publish(
                event_type="risk_alert",
                payload=action.model_dump(),
            )

            if "containment" in action.action.lower():
                self.create_task(
                    title=f"Risk containment: {action.action[:80]}",
                    description=action.action,
                    priority=1,
                )

            if "ethics audit" in action.action.lower():
                self.create_task(
                    title=f"Ethics audit: {action.action[:80]}",
                    description=action.action,
                    priority=2,
                )

            self._update_risk_ontology_node(action)

        logger.info("[%s] emitted %d actions", self.role_id, len(actions))

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _compute_risk_score_for_peer_anomaly(anomaly: Dict) -> float:
        payload = anomaly.get("payload", {})
        p = float(payload.get("probability", 0.5))
        impact = float(payload.get("impact", 10_000))
        velocity = float(payload.get("velocity", 1.0))
        interdep = float(payload.get("interdependency", 0.2))
        td = float(payload.get("truth_deviation", 0.1))
        return p * impact * velocity * (1 + interdep) * td

    def _update_risk_ontology_node(self, action: ActionOutput) -> None:
        node = OntologyNode(
            entity="risk_action",
            attributes={
                "action": action.action,
                "projected_roi": action.projected_roi,
                "source_agent": self.role_id,
            },
            causal_relations=[{
                "target": "mitigation_outcome",
                "relation": "mitigates",
                "weight": action.projected_roi / 10.0,
                "confidence": action.roi_ci.confidence,
            }],
            quantitative_thresholds={
                "rev_alert": REV_ALERT_THRESHOLD,
                "cvar_99_9": CVAR_99_9_THRESHOLD,
                "ethics_floor": ETHICS_INTEGRITY_FLOOR,
            },
            statistical_confidence=action.roi_ci.confidence,
            self_correction_triggers=[action.kill_criteria],
            derivative_intelligence_hooks=["mitigation_roi_recalc", "bayesian_posterior_update"],
            roi_projection_link=action.action[:64],
        )
        self.upsert_ontology_node(node)
