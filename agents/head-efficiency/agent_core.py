"""Head of Efficiency — L5 Agent #12

Maximize operational leverage through first-principles identification and
elevation of constraints. Applies Musk Algorithm, Theory of Constraints,
Lean, and Little's Law to detect bottlenecks, waste patterns, and cycle
time spikes, then emits constraint-elevation and flow-acceleration actions.
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

logger = logging.getLogger("eve.l5.head-efficiency")

# ---------------------------------------------------------------------------
# Thresholds & constants
# ---------------------------------------------------------------------------

UTILIZATION_CEILING = 0.92
UTILIZATION_FLOOR = 0.70
OEE_FLOOR = 0.75
CYCLE_TIME_SPIKE_MULTIPLIER = 1.5
PROCESS_CYCLE_EFFICIENCY_FLOOR = 0.40
CONSTRAINT_ELEVATION_VELOCITY_FLOOR = 1  # elevations per quarter


class HeadEfficiencyAgent(L5AgentBase):
    """Detects constraint violations and waste, emits flow-acceleration actions."""

    role_id: ClassVar[str] = "head-efficiency"
    display_name: ClassVar[str] = "Head of Efficiency"
    cadence_seconds: ClassVar[int] = 60
    poll_tables: ClassVar[List[str]] = [
        "resource_capacity",
        "throughput_ledger",
        "variability_metrics",
        "ontology_nodes",
        "outbox",
    ]

    vanity_metrics: ClassVar[List[str]] = [
        "gross_procedure_volume",
        "total_headcount",
        "superficial_busyness",
        "non_constraint_utilization",
        "process_theater",
    ]

    signal_metrics: ClassVar[List[str]] = [
        "bottleneck_utilization",
        "inventory_turns",
        "true_cost_per_procedure",
        "contribution_margin_per_chair_hour",
        "oee",
        "process_cycle_efficiency",
        "constraint_elevation_velocity",
        "feedback_loop_speed",
    ]

    # -- Pipeline stages ----------------------------------------------------

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []

        for row in data.get("resource_capacity", []):
            utilization = row.get("utilization")
            if utilization is not None:
                if utilization > UTILIZATION_CEILING:
                    anomalies.append({
                        "type": "constraint_overload",
                        "entity": row.get("resource_id", row.get("entity", "unknown")),
                        "value": utilization,
                        "threshold": UTILIZATION_CEILING,
                        "severity": "high",
                        "detail": "Utilization exceeds ceiling — overload risk on constraint",
                    })
                elif utilization < UTILIZATION_FLOOR:
                    is_constraint = row.get("is_binding_constraint", False)
                    if is_constraint:
                        anomalies.append({
                            "type": "constraint_underutilization",
                            "entity": row.get("resource_id", row.get("entity", "unknown")),
                            "value": utilization,
                            "threshold": UTILIZATION_FLOOR,
                            "severity": "high",
                            "detail": "Binding constraint underutilized — throughput being left on table",
                        })

            oee = row.get("oee")
            if oee is not None and oee < OEE_FLOOR:
                anomalies.append({
                    "type": "oee_degradation",
                    "entity": row.get("resource_id", row.get("entity", "unknown")),
                    "value": oee,
                    "threshold": OEE_FLOOR,
                    "severity": "medium",
                })

        for row in data.get("throughput_ledger", []):
            cycle_time = row.get("cycle_time_minutes")
            baseline = row.get("baseline_cycle_time_minutes")
            if cycle_time is not None and baseline is not None:
                if cycle_time > baseline * CYCLE_TIME_SPIKE_MULTIPLIER:
                    anomalies.append({
                        "type": "cycle_time_spike",
                        "entity": row.get("procedure_type", "unknown"),
                        "value": cycle_time,
                        "baseline": baseline,
                        "threshold": baseline * CYCLE_TIME_SPIKE_MULTIPLIER,
                        "severity": "high",
                    })

            pce = row.get("process_cycle_efficiency")
            if pce is not None and pce < PROCESS_CYCLE_EFFICIENCY_FLOOR:
                anomalies.append({
                    "type": "low_process_cycle_efficiency",
                    "entity": row.get("procedure_type", "unknown"),
                    "value": pce,
                    "threshold": PROCESS_CYCLE_EFFICIENCY_FLOOR,
                    "severity": "medium",
                    "detail": "High ratio of non-value-add time — Muda detected",
                })

        for row in data.get("variability_metrics", []):
            cv = row.get("coefficient_of_variation")
            if cv is not None and cv > 0.5:
                anomalies.append({
                    "type": "mura_unevenness",
                    "entity": row.get("process", row.get("entity", "unknown")),
                    "value": cv,
                    "threshold": 0.5,
                    "severity": "medium",
                    "detail": "High process variability (Mura) — destabilizing flow",
                })

            overburden = row.get("overburden_score")
            if overburden is not None and overburden > 0.8:
                anomalies.append({
                    "type": "muri_overburden",
                    "entity": row.get("process", row.get("entity", "unknown")),
                    "value": overburden,
                    "threshold": 0.8,
                    "severity": "high",
                    "detail": "Resource overburden (Muri) — unsustainable load",
                })

        for msg in data.get("_inbox", []):
            if msg.get("event_type") in (
                "growth.demand_signal",
                "talent.performance_update",
                "innovation.deployment_trigger",
            ):
                anomalies.append({
                    "type": "cross_agent_efficiency_signal",
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

            if atype == "constraint_overload":
                excess = anomaly["value"] - UTILIZATION_CEILING
                roi_lower = excess * 100_000
                roi_upper = excess * 300_000
                actions.append(ActionOutput(
                    action=f"Elevate constraint '{anomaly.get('entity')}' — "
                           f"utilization={anomaly['value']:.2f} exceeds {UTILIZATION_CEILING}. "
                           f"Musk step 1: question requirement driving overload",
                    projected_roi=round((roi_lower + roi_upper) / 2, 2),
                    roi_ci=ConfidenceInterval(lower=round(roi_lower, 2), upper=round(roi_upper, 2)),
                    validation_plan="Track utilization weekly for 4 weeks post-elevation; "
                                    "measure throughput delta and margin impact.",
                    kill_criteria="Abort if utilization does not drop below 0.92 within 3 weeks.",
                ))

            elif atype == "constraint_underutilization":
                gap = UTILIZATION_FLOOR - anomaly["value"]
                roi_lower = gap * 80_000
                roi_upper = gap * 200_000
                actions.append(ActionOutput(
                    action=f"Exploit constraint '{anomaly.get('entity')}' — "
                           f"binding constraint at {anomaly['value']:.2f} utilization, "
                           f"leaving throughput on table",
                    projected_roi=round((roi_lower + roi_upper) / 2, 2),
                    roi_ci=ConfidenceInterval(lower=round(roi_lower, 2), upper=round(roi_upper, 2)),
                    validation_plan="Increase constraint loading; measure throughput and margin at "
                                    "weekly intervals.",
                    kill_criteria="Abort if utilization increase does not lift throughput within 2 weeks.",
                ))

            elif atype == "cycle_time_spike":
                time_excess = anomaly["value"] - anomaly.get("baseline", anomaly["value"])
                roi_per_min = 150
                actions.append(ActionOutput(
                    action=f"Investigate cycle time spike for '{anomaly.get('entity')}' — "
                           f"{anomaly['value']}min vs {anomaly.get('baseline')}min baseline. "
                           f"Apply Lean root cause analysis",
                    projected_roi=round(time_excess * roi_per_min, 2),
                    roi_ci=ConfidenceInterval(
                        lower=round(time_excess * roi_per_min * 0.5, 2),
                        upper=round(time_excess * roi_per_min * 2.0, 2),
                    ),
                    validation_plan="Identify root cause within 48h; implement fix; "
                                    "track cycle time for 2 weeks.",
                    kill_criteria="Abort if root cause not identified within 72h.",
                ))

            elif atype == "low_process_cycle_efficiency":
                waste_ratio = 1.0 - anomaly["value"]
                actions.append(ActionOutput(
                    action=f"Eliminate non-value-add time for '{anomaly.get('entity')}' — "
                           f"PCE={anomaly['value']:.2f} ({waste_ratio:.0%} waste). "
                           f"Musk step 2: delete unnecessary steps",
                    projected_roi=round(waste_ratio * 40_000, 2),
                    roi_ci=ConfidenceInterval(
                        lower=round(waste_ratio * 15_000, 2),
                        upper=round(waste_ratio * 70_000, 2),
                    ),
                    validation_plan="Map value stream; remove identified Muda; "
                                    "measure PCE improvement over 4 weeks.",
                    kill_criteria="Abort if PCE does not improve >=10pp within 4 weeks.",
                ))

            elif atype == "oee_degradation":
                gap = OEE_FLOOR - anomaly["value"]
                actions.append(ActionOutput(
                    action=f"Restore OEE for '{anomaly.get('entity')}' — "
                           f"OEE={anomaly['value']:.2f}, floor={OEE_FLOOR}. "
                           f"Decompose availability × performance × quality",
                    projected_roi=round(gap * 60_000, 2),
                    roi_ci=ConfidenceInterval(
                        lower=round(gap * 25_000, 2),
                        upper=round(gap * 100_000, 2),
                    ),
                    validation_plan="Identify weakest OEE factor; target improvement; "
                                    "measure OEE weekly for 6 weeks.",
                    kill_criteria="Abort if OEE does not reach 0.75 within 6 weeks.",
                ))

            elif atype in ("mura_unevenness", "muri_overburden"):
                waste_type = "Mura (unevenness)" if atype == "mura_unevenness" else "Muri (overburden)"
                actions.append(ActionOutput(
                    action=f"Eliminate {waste_type} on '{anomaly.get('entity')}' — "
                           f"score={anomaly['value']:.2f}",
                    projected_roi=20_000.0,
                    roi_ci=ConfidenceInterval(lower=8_000.0, upper=40_000.0),
                    validation_plan=f"Implement leveling/load-balancing; track variability metric "
                                    f"for 4 weeks.",
                    kill_criteria=f"Abort if {waste_type} metric does not improve >=20% in 4 weeks.",
                ))

            elif atype == "cross_agent_efficiency_signal":
                actions.append(ActionOutput(
                    action=f"Evaluate constraint impact of {anomaly.get('event_type')} "
                           f"from {anomaly.get('source')}",
                    projected_roi=0.0,
                    roi_ci=ConfidenceInterval(lower=0.0, upper=0.0),
                    validation_plan="Cross-reference with constraint model; respond within 1 tick.",
                    kill_criteria="Discard if no constraint impact identified.",
                ))

        logger.info("[%s] derived %d actions", self.role_id, len(actions))
        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for action in actions:
            self.publish(
                event_type="efficiency.action",
                payload=action.model_dump(),
            )

            if "constraint" in action.action.lower() or "elevate" in action.action.lower():
                self.publish(
                    event_type="efficiency.constraint_report",
                    payload=action.model_dump(),
                )

            if any(kw in action.action.lower() for kw in ("waste", "muda", "mura", "muri", "eliminate")):
                self.publish(
                    event_type="efficiency.waste_alert",
                    payload=action.model_dump(),
                )

            if "cycle time" in action.action.lower() or "pce" in action.action.lower():
                self.create_task(
                    title=f"[Efficiency] {action.action[:80]}",
                    description=action.action,
                    priority=2,
                )
                self.publish(
                    event_type="efficiency.process_optimization",
                    payload=action.model_dump(),
                )

            if "throughput" in action.action.lower():
                self.publish(
                    event_type="efficiency.throughput_change",
                    payload=action.model_dump(),
                    target="head-patient-experience",
                )

        logger.info("[%s] emitted %d actions", self.role_id, len(actions))
