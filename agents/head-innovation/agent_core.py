"""Head of Innovation — L5 Agent #11

Simulate, synthesize cross-domain, and deploy high-leverage capabilities.
Scans for stale capabilities, untested assumptions, and cross-domain synergies
to emit simulation-validated innovation proposals with measured ROI.
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

logger = logging.getLogger("eve.l5.head-innovation")

# ---------------------------------------------------------------------------
# Thresholds & constants
# ---------------------------------------------------------------------------

TIME_TO_VALUE_CEILING_DAYS = 90
SIMULATION_FIDELITY_FLOOR = 0.80
ASSUMPTION_KILL_RATE_FLOOR = 0.20
LEVERAGE_MULTIPLIER_FLOOR = 2.0
STALENESS_THRESHOLD_DAYS = 30


class HeadInnovationAgent(L5AgentBase):
    """Detects innovation opportunities and emits simulation-validated proposals."""

    role_id: ClassVar[str] = "head-innovation"
    display_name: ClassVar[str] = "Head of Innovation"
    cadence_seconds: ClassVar[int] = 120
    poll_tables: ClassVar[List[str]] = [
        "ontology_nodes",
        "tasks",
        "outbox",
    ]

    vanity_metrics: ClassVar[List[str]] = [
        "idea_volume",
        "undeployed_patents",
        "rd_spend",
        "hype",
        "consensus_alignment",
    ]

    signal_metrics: ClassVar[List[str]] = [
        "innovation_roi",
        "time_to_value",
        "leverage_multiplier",
        "simulation_fidelity",
        "assumption_kill_rate",
        "fcf_impact",
        "revenue_per_employee_impact",
        "clinical_outcome_impact",
    ]

    # -- Pipeline stages ----------------------------------------------------

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []

        for row in data.get("ontology_nodes", []):
            attrs = row.get("attributes", {})

            days_since_update = attrs.get("days_since_last_improvement")
            if days_since_update is not None and days_since_update > STALENESS_THRESHOLD_DAYS:
                anomalies.append({
                    "type": "stale_capability",
                    "entity": row.get("entity"),
                    "value": days_since_update,
                    "threshold": STALENESS_THRESHOLD_DAYS,
                    "severity": "medium",
                    "node_id": row.get("node_id"),
                })

            assumption_status = attrs.get("assumption_tested")
            if assumption_status is False:
                anomalies.append({
                    "type": "untested_assumption",
                    "entity": row.get("entity"),
                    "assumption": attrs.get("assumption_description", "unknown"),
                    "severity": "medium",
                    "node_id": row.get("node_id"),
                })

            leverage = attrs.get("leverage_multiplier")
            if leverage is not None and leverage >= LEVERAGE_MULTIPLIER_FLOOR:
                sim_fidelity = attrs.get("simulation_fidelity", 0)
                if sim_fidelity < SIMULATION_FIDELITY_FLOOR:
                    anomalies.append({
                        "type": "high_leverage_opportunity",
                        "entity": row.get("entity"),
                        "leverage": leverage,
                        "simulation_fidelity": sim_fidelity,
                        "severity": "high",
                        "node_id": row.get("node_id"),
                    })

        cross_domain_signals: Dict[str, List[Dict]] = {}
        for msg in data.get("_inbox", []):
            source = msg.get("source_agent", "unknown")
            cross_domain_signals.setdefault(source, []).append(msg)

        if len(cross_domain_signals) >= 2:
            anomalies.append({
                "type": "cross_domain_synergy",
                "domains": list(cross_domain_signals.keys()),
                "signal_count": sum(len(v) for v in cross_domain_signals.values()),
                "severity": "high",
            })

        for msg in data.get("_inbox", []):
            if msg.get("event_type", "").endswith("constraint_report"):
                anomalies.append({
                    "type": "constraint_innovation_opportunity",
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

            if atype == "stale_capability":
                actions.append(ActionOutput(
                    action=f"Investigate stale capability '{anomaly.get('entity', 'unknown')}' "
                           f"({anomaly['value']} days without improvement); "
                           f"design first-principles decomposition",
                    projected_roi=20_000.0,
                    roi_ci=ConfidenceInterval(lower=5_000.0, upper=50_000.0),
                    validation_plan="Define improvement hypothesis; simulate within 2 weeks; "
                                    "measure capability delta.",
                    kill_criteria="Abort if no viable improvement hypothesis within 1 week.",
                ))

            elif atype == "untested_assumption":
                actions.append(ActionOutput(
                    action=f"Design assumption test for '{anomaly.get('assumption')}' "
                           f"on entity '{anomaly.get('entity', 'unknown')}'",
                    projected_roi=10_000.0,
                    roi_ci=ConfidenceInterval(lower=0.0, upper=30_000.0),
                    validation_plan="Run controlled test; compare outcome to assumption prediction; "
                                    "kill or validate within 30 days.",
                    kill_criteria="Kill assumption if test contradicts prediction at p<0.05.",
                ))

            elif atype == "high_leverage_opportunity":
                leverage = anomaly.get("leverage", LEVERAGE_MULTIPLIER_FLOOR)
                roi_base = leverage * 25_000
                actions.append(ActionOutput(
                    action=f"Design simulation for high-leverage opportunity "
                           f"'{anomaly.get('entity', 'unknown')}' "
                           f"(leverage={leverage:.1f}x, sim fidelity={anomaly.get('simulation_fidelity', 0):.2f})",
                    projected_roi=round(roi_base, 2),
                    roi_ci=ConfidenceInterval(
                        lower=round(roi_base * 0.4, 2),
                        upper=round(roi_base * 2.0, 2),
                    ),
                    validation_plan="Build simulation with fidelity target >=0.80; "
                                    "validate against 3 historical scenarios.",
                    kill_criteria=f"Abort if simulation fidelity < {SIMULATION_FIDELITY_FLOOR} "
                                  f"after 2 iterations.",
                ))

            elif atype == "cross_domain_synergy":
                domains = anomaly.get("domains", [])
                actions.append(ActionOutput(
                    action=f"Synthesize cross-domain innovation from {', '.join(domains)} "
                           f"({anomaly.get('signal_count', 0)} signals)",
                    projected_roi=50_000.0,
                    roi_ci=ConfidenceInterval(lower=15_000.0, upper=120_000.0),
                    validation_plan="Design cross-domain experiment; measure combined impact "
                                    "vs. isolated domain actions.",
                    kill_criteria="Abort if combined impact is not >1.5x isolated sum.",
                ))

            elif atype == "constraint_innovation_opportunity":
                actions.append(ActionOutput(
                    action=f"Evaluate constraint dissolution via innovation for "
                           f"{anomaly.get('event_type')} from {anomaly.get('source')}",
                    projected_roi=30_000.0,
                    roi_ci=ConfidenceInterval(lower=10_000.0, upper=60_000.0),
                    validation_plan="Determine if constraint is solvable through innovation "
                                    "rather than optimization; propose solution within 1 week.",
                    kill_criteria="Discard if constraint is not innovation-solvable.",
                ))

        logger.info("[%s] derived %d actions", self.role_id, len(actions))
        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for action in actions:
            self.publish(
                event_type="innovation.action",
                payload=action.model_dump(),
            )

            if "simulation" in action.action.lower():
                self.publish(
                    event_type="innovation.simulation_result",
                    payload=action.model_dump(),
                )

            if "cross-domain" in action.action.lower() or "synergy" in action.action.lower():
                self.publish(
                    event_type="innovation.proposal",
                    payload=action.model_dump(),
                )

            if "assumption" in action.action.lower() and "kill" in action.kill_criteria.lower():
                self.publish(
                    event_type="innovation.assumption_killed",
                    payload=action.model_dump(),
                )

            if "deploy" in action.action.lower():
                self.create_task(
                    title=f"[Innovation] {action.action[:80]}",
                    description=action.action,
                    priority=2,
                )
                self.publish(
                    event_type="innovation.deployment_trigger",
                    payload=action.model_dump(),
                )

        logger.info("[%s] emitted %d actions", self.role_id, len(actions))
