"""Head of Patient Acquisition — Eve L5 Agent."""

from __future__ import annotations

import logging
import statistics
from typing import Any, ClassVar, Dict, List, Optional

from agents.l5.base import (
    ActionOutput,
    ConfidenceInterval,
    L5AgentBase,
    OntologyNode,
)

logger = logging.getLogger("eve.l5.patient_acquisition")


class HeadPatientAcquisition(L5AgentBase):
    role_id: ClassVar[str] = "head-patient-acquisition"
    display_name: ClassVar[str] = "Head of Patient Acquisition"
    cadence_seconds: ClassVar[int] = 120
    poll_tables: ClassVar[List[str]] = [
        "leads_queue", "throughput_ledger", "ontology_nodes", "outbox",
    ]

    vanity_metrics: ClassVar[List[str]] = [
        "Total impressions", "Clicks", "CTR", "CPC",
        "Raw lead volume", "Social followers", "Likes",
        "Engagement rate", "Brand awareness", "Total ad spend",
    ]

    signal_metrics: ClassVar[List[str]] = [
        "Incrementality-tested marginal ROI", "CAC per channel",
        "Realized LTV", "Payback period", "Contribution margin by cohort",
        "Cohort retention 3mo", "Cohort retention 6mo",
        "Cohort retention 12mo", "Experiment velocity",
        "Direct lift to FCF",
    ]

    CAC_SPIKE_THRESHOLD = 0.20
    LTV_CAC_MIN = 3.0
    PAYBACK_MONTHS_MAX = 6
    EXPERIMENT_VELOCITY_MIN = 3
    RETENTION_3MO_MIN = 0.70
    RETENTION_6MO_MIN = 0.55
    RETENTION_12MO_MIN = 0.40

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []

        leads = data.get("leads_queue", [])
        by_channel: Dict[str, List[Dict]] = {}
        for lead in leads:
            ch = lead.get("channel", "unknown")
            by_channel.setdefault(ch, []).append(lead)

        for channel, channel_leads in by_channel.items():
            cacs = [l.get("cac", 0) for l in channel_leads if l.get("cac") is not None]
            if len(cacs) >= 2:
                recent_cac = statistics.mean(cacs[-5:]) if len(cacs) >= 5 else statistics.mean(cacs)
                baseline_cac = statistics.mean(cacs)
                if baseline_cac > 0:
                    spike_pct = (recent_cac - baseline_cac) / baseline_cac
                    if spike_pct > self.CAC_SPIKE_THRESHOLD:
                        anomalies.append({
                            "type": "cac_spike",
                            "channel": channel,
                            "recent_cac": recent_cac,
                            "baseline_cac": baseline_cac,
                            "spike_pct": spike_pct,
                            "severity": min(spike_pct / 0.50, 1.0),
                        })

            ltv_cacs = [l.get("ltv_cac_ratio", 0) for l in channel_leads if l.get("ltv_cac_ratio") is not None]
            if ltv_cacs:
                avg_ltv_cac = statistics.mean(ltv_cacs)
                if avg_ltv_cac < self.LTV_CAC_MIN:
                    anomalies.append({
                        "type": "ltv_cac_degradation",
                        "channel": channel,
                        "ratio": avg_ltv_cac,
                        "threshold": self.LTV_CAC_MIN,
                        "severity": min((self.LTV_CAC_MIN - avg_ltv_cac) / 2.0, 1.0),
                    })

            conversions = [l for l in channel_leads if l.get("converted")]
            conv_rate = len(conversions) / max(len(channel_leads), 1)
            if conv_rate < 0.10 and len(channel_leads) >= 10:
                anomalies.append({
                    "type": "channel_underperformance",
                    "channel": channel,
                    "conversion_rate": conv_rate,
                    "lead_count": len(channel_leads),
                    "severity": min((0.20 - conv_rate) / 0.20, 1.0),
                })

        nodes = data.get("ontology_nodes", [])
        for node in nodes:
            if node.get("entity") == "experiment_tracker":
                velocity = node.get("attributes", {}).get("tests_per_week", 0)
                if isinstance(velocity, (int, float)) and velocity < self.EXPERIMENT_VELOCITY_MIN:
                    anomalies.append({
                        "type": "experiment_velocity_drop",
                        "current_velocity": velocity,
                        "threshold": self.EXPERIMENT_VELOCITY_MIN,
                        "severity": min((self.EXPERIMENT_VELOCITY_MIN - velocity) / self.EXPERIMENT_VELOCITY_MIN, 1.0),
                    })

        for node in nodes:
            if node.get("entity") == "cohort_retention":
                attrs = node.get("attributes", {})
                for period, min_rate in [("3mo", self.RETENTION_3MO_MIN), ("6mo", self.RETENTION_6MO_MIN), ("12mo", self.RETENTION_12MO_MIN)]:
                    rate = attrs.get(f"retention_{period}")
                    if rate is not None and rate < min_rate:
                        anomalies.append({
                            "type": "cohort_retention_decay",
                            "period": period,
                            "rate": rate,
                            "threshold": min_rate,
                            "cohort_id": node.get("node_id", "unknown"),
                            "severity": min((min_rate - rate) / min_rate, 1.0),
                        })

        return anomalies

    def derive_intelligence(self, anomalies: List[Dict], data: Dict[str, List[Dict]]) -> List[ActionOutput]:
        actions: List[ActionOutput] = []

        cac_spikes = [a for a in anomalies if a["type"] == "cac_spike"]
        for cs in sorted(cac_spikes, key=lambda x: x["severity"], reverse=True)[:3]:
            savings = cs["recent_cac"] - cs["baseline_cac"]
            volume = len(data.get("leads_queue", []))
            roi = savings * volume * 0.5
            actions.append(ActionOutput(
                action=(
                    f"REALLOCATE_BUDGET:channel={cs['channel']}:"
                    f"reduce_by={cs['spike_pct']:.2%}"
                ),
                projected_roi=roi,
                roi_ci=ConfidenceInterval(lower=roi * 0.5, upper=roi * 1.5),
                validation_plan=(
                    f"CAC for {cs['channel']} must return to "
                    f"<=${cs['baseline_cac']:.2f} within 14 days"
                ),
                kill_criteria=(
                    f"CAC still >{cs['baseline_cac'] * 1.3:.2f} after 21 days "
                    f"— kill channel and reallocate 100% of budget"
                ),
            ))

        ltv_cac_issues = [a for a in anomalies if a["type"] == "ltv_cac_degradation"]
        for lc in sorted(ltv_cac_issues, key=lambda x: x["severity"], reverse=True)[:3]:
            roi = lc["severity"] * 20_000
            actions.append(ActionOutput(
                action=f"SCALE_DOWN_CHANNEL:channel={lc['channel']}:ltv_cac={lc['ratio']:.2f}",
                projected_roi=roi,
                roi_ci=ConfidenceInterval(lower=roi * 0.6, upper=roi * 1.4),
                validation_plan=(
                    f"LTV:CAC for {lc['channel']} must reach "
                    f">={self.LTV_CAC_MIN:.1f} within 30 days or channel is killed"
                ),
                kill_criteria=f"LTV:CAC still <{self.LTV_CAC_MIN - 0.5:.1f} after 45 days — permanent kill",
            ))

        underperformers = [a for a in anomalies if a["type"] == "channel_underperformance"]
        for up in underperformers:
            roi = up["severity"] * 10_000
            actions.append(ActionOutput(
                action=(
                    f"KILL_CHANNEL:channel={up['channel']}:"
                    f"conv_rate={up['conversion_rate']:.4f}:"
                    f"leads={up['lead_count']}"
                ),
                projected_roi=roi,
                roi_ci=ConfidenceInterval(lower=roi * 0.7, upper=roi * 1.3),
                validation_plan="Reallocated budget must produce >15% conversion rate in target channels within 14 days",
                kill_criteria="Reallocated budget performs worse than killed channel — reverse and investigate",
            ))

        vel_drops = [a for a in anomalies if a["type"] == "experiment_velocity_drop"]
        for vd in vel_drops:
            actions.append(ActionOutput(
                action=f"BOOST_EXPERIMENT_VELOCITY:current={vd['current_velocity']}:target={self.EXPERIMENT_VELOCITY_MIN}",
                projected_roi=15_000,
                roi_ci=ConfidenceInterval(lower=8_000, upper=25_000),
                validation_plan=f"Experiment velocity must reach >={self.EXPERIMENT_VELOCITY_MIN} tests/week within 7 days",
                kill_criteria="Velocity still <2/week after 14 days — audit experiment infrastructure",
            ))

        retention_decays = [a for a in anomalies if a["type"] == "cohort_retention_decay"]
        for rd in retention_decays:
            roi = rd["severity"] * 12_000
            actions.append(ActionOutput(
                action=f"RETENTION_INTERVENTION:cohort={rd['cohort_id']}:period={rd['period']}:rate={rd['rate']:.4f}",
                projected_roi=roi,
                roi_ci=ConfidenceInterval(lower=roi * 0.5, upper=roi * 1.5),
                validation_plan=f"Cohort {rd['period']} retention must reach >={rd['threshold']:.0%} within 30 days",
                kill_criteria=f"Retention still declining after 60 days — flag cohort for deep investigation",
            ))

        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for act in actions:
            self.publish(
                event_type="acquisition_action",
                payload=act.model_dump(),
            )
            if "KILL_CHANNEL" in act.action:
                self.publish(
                    event_type="channel_kill",
                    payload=act.model_dump(),
                    target="chief-financial-officer",
                )
                self.create_task(
                    title=f"Kill underperforming channel: {act.action.split(':')[1]}",
                    description=act.action,
                    priority=1,
                )
            if "REALLOCATE_BUDGET" in act.action:
                self.publish(
                    event_type="budget_reallocation",
                    payload=act.model_dump(),
                    target="chief-financial-officer",
                )
            if "RETENTION_INTERVENTION" in act.action:
                self.publish(
                    event_type="retention_alert",
                    payload=act.model_dump(),
                    target="head-revenue-operations",
                )
            logger.info("[%s] emitted: %s", self.role_id, act.action)

    def evaluate_channel(self, channel: str, leads: List[Dict]) -> Dict[str, Any]:
        cacs = [l.get("cac", 0) for l in leads if l.get("cac") is not None]
        ltvs = [l.get("ltv", 0) for l in leads if l.get("ltv") is not None]
        conversions = sum(1 for l in leads if l.get("converted"))

        avg_cac = statistics.mean(cacs) if cacs else 0
        avg_ltv = statistics.mean(ltvs) if ltvs else 0
        conv_rate = conversions / max(len(leads), 1)

        return {
            "channel": channel,
            "lead_count": len(leads),
            "avg_cac": avg_cac,
            "avg_ltv": avg_ltv,
            "ltv_cac_ratio": avg_ltv / max(avg_cac, 1),
            "conversion_rate": conv_rate,
            "marginal_roi": (avg_ltv - avg_cac) / max(avg_cac, 1),
            "recommendation": "scale" if avg_ltv / max(avg_cac, 1) > 4.5 else "hold" if avg_ltv / max(avg_cac, 1) > 3.0 else "kill",
        }

    def analyze_cohort(self, cohort_id: str, patients: List[Dict]) -> Dict[str, Any]:
        total = len(patients)
        active_3mo = sum(1 for p in patients if p.get("active_3mo"))
        active_6mo = sum(1 for p in patients if p.get("active_6mo"))
        active_12mo = sum(1 for p in patients if p.get("active_12mo"))

        margins = [p.get("contribution_margin", 0) for p in patients if p.get("contribution_margin") is not None]
        avg_margin = statistics.mean(margins) if margins else 0

        return {
            "cohort_id": cohort_id,
            "total_patients": total,
            "retention_3mo": active_3mo / max(total, 1),
            "retention_6mo": active_6mo / max(total, 1),
            "retention_12mo": active_12mo / max(total, 1),
            "avg_contribution_margin": avg_margin,
            "cohort_ltv": avg_margin * 12,
        }
