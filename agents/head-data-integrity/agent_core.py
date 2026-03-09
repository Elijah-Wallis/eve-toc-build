"""
Head of Real World Proprietary Data Integrity Analytics — L5 Agent Core
========================================================================
Converts proprietary real-world clinic data streams into causally
identified predictive engines.
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

logger = logging.getLogger("eve.l5.head-data-integrity")

# ---------------------------------------------------------------------------
# Thresholds & constants
# ---------------------------------------------------------------------------

BRIER_SCORE_MAX = 0.05
CONCEPT_DRIFT_PSI_MAX = 0.10
PROVENANCE_COMPLETENESS_MIN = 1.0
BIAS_RATIO_MAX = 0.05


class HeadDataIntegrityAgent(L5AgentBase):
    """L5 autonomous agent for proprietary data integrity and predictive fidelity."""

    role_id: ClassVar[str] = "head-data-integrity"
    display_name: ClassVar[str] = "Head of Real World Proprietary Data Integrity Analytics"
    cadence_seconds: ClassVar[int] = 60
    poll_tables: ClassVar[List[str]] = [
        "ontology_nodes",
        "throughput_ledger",
        "leads_queue",
        "outbox",
    ]
    vanity_metrics: ClassVar[List[str]] = [
        "raw_volume",
        "in_sample_r2",
        "model_complexity",
        "p_value_only",
        "dashboard_count",
    ]
    signal_metrics: ClassVar[List[str]] = [
        "oos_brier_score",
        "experiment_attributed_ate",
        "intervention_roi_lift",
        "proprietary_moat_durability",
    ]

    # -- Pipeline stages ----------------------------------------------------

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []
        nodes = data.get("ontology_nodes", [])

        for node in nodes:
            attrs = node.get("attributes", {})

            brier = attrs.get("oos_brier")
            if brier is not None and brier > BRIER_SCORE_MAX:
                anomalies.append({
                    "type": "calibration_degradation",
                    "entity": node.get("entity"),
                    "value": brier,
                    "threshold": BRIER_SCORE_MAX,
                    "severity": "critical",
                })

            psi = attrs.get("concept_drift_psi")
            if psi is not None and psi > CONCEPT_DRIFT_PSI_MAX:
                anomalies.append({
                    "type": "concept_drift",
                    "entity": node.get("entity"),
                    "value": psi,
                    "threshold": CONCEPT_DRIFT_PSI_MAX,
                    "severity": "high",
                })

            provenance = attrs.get("provenance_completeness")
            if provenance is not None and provenance < PROVENANCE_COMPLETENESS_MIN:
                anomalies.append({
                    "type": "data_provenance_failure",
                    "entity": node.get("entity"),
                    "value": provenance,
                    "threshold": PROVENANCE_COMPLETENESS_MIN,
                    "severity": "critical",
                })

            bias_ratio = attrs.get("bias_ratio")
            if bias_ratio is not None and bias_ratio > BIAS_RATIO_MAX:
                anomalies.append({
                    "type": "bias_anomaly",
                    "entity": node.get("entity"),
                    "value": bias_ratio,
                    "threshold": BIAS_RATIO_MAX,
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

            if atype == "calibration_degradation":
                actions.append(ActionOutput(
                    action=(
                        f"Trigger model recalibration for {anomaly['entity']}; "
                        f"Brier score {anomaly['value']:.4f} exceeds "
                        f"threshold {anomaly['threshold']}"
                    ),
                    projected_roi=3.0,
                    roi_ci=ConfidenceInterval(lower=1.5, upper=5.0),
                    validation_plan=(
                        "Retrain on latest 90-day window; validate OOS Brier "
                        "score on held-out 30-day set; compare to pre-retrain baseline"
                    ),
                    kill_criteria=(
                        "Revert to previous model version if post-retrain "
                        "Brier score does not improve by ≥10%"
                    ),
                ))

            elif atype == "concept_drift":
                actions.append(ActionOutput(
                    action=(
                        f"Initiate drift remediation for {anomaly['entity']}; "
                        f"PSI at {anomaly['value']:.4f} vs "
                        f"{anomaly['threshold']} threshold"
                    ),
                    projected_roi=2.5,
                    roi_ci=ConfidenceInterval(lower=1.0, upper=4.5),
                    validation_plan=(
                        "Identify drifted features via per-feature PSI decomposition; "
                        "retrain with updated feature distributions; "
                        "validate stability over 14-day monitoring window"
                    ),
                    kill_criteria=(
                        "Halt if drift is caused by data pipeline error rather "
                        "than genuine distributional shift; fix pipeline first"
                    ),
                ))

            elif atype == "data_provenance_failure":
                actions.append(ActionOutput(
                    action=(
                        f"Halt downstream consumption for {anomaly['entity']}; "
                        f"provenance completeness at {anomaly['value']:.2%}"
                    ),
                    projected_roi=4.0,
                    roi_ci=ConfidenceInterval(lower=2.0, upper=7.0),
                    validation_plan=(
                        "Trace lineage gap to source system; repair and "
                        "re-validate full provenance chain before resuming"
                    ),
                    kill_criteria=(
                        "Keep downstream halted until provenance completeness "
                        "reaches 100%; no exceptions"
                    ),
                ))

            elif atype == "bias_anomaly":
                actions.append(ActionOutput(
                    action=(
                        f"Launch bias audit for {anomaly['entity']}; "
                        f"bias ratio at {anomaly['value']:.4f}"
                    ),
                    projected_roi=2.0,
                    roi_ci=ConfidenceInterval(lower=0.8, upper=3.5),
                    validation_plan=(
                        "Run stratified fairness analysis across demographic "
                        "subgroups; apply debiasing if warranted; "
                        "revalidate OOS performance"
                    ),
                    kill_criteria=(
                        "Revert debiasing if OOS calibration degrades by "
                        ">5% or if bias ratio does not decrease"
                    ),
                ))

        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for action in actions:
            event_type = "integrity_alert"
            if "recalibration" in action.action.lower():
                event_type = "model_retrain_trigger"
            elif "prediction" in action.action.lower():
                event_type = "prediction_update"

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
