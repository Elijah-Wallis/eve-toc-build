"""Head of Revenue Operations — Eve L5 Agent."""

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

logger = logging.getLogger("eve.l5.revenue_ops")


class HeadRevenueOperations(L5AgentBase):
    role_id: ClassVar[str] = "head-revenue-operations"
    display_name: ClassVar[str] = "Head of Revenue Operations"
    cadence_seconds: ClassVar[int] = 120
    poll_tables: ClassVar[List[str]] = [
        "throughput_ledger", "leads_queue", "resource_capacity",
        "variability_metrics", "outbox",
    ]

    vanity_metrics: ClassVar[List[str]] = [
        "Followers", "Likes", "Brand Awareness", "Verbal Commitments",
        "Networking", "Unadjusted Gross Revenue", "Headcount",
    ]

    signal_metrics: ClassVar[List[str]] = [
        "Conversion Velocity", "Referral Rate", "Revenue per Patient",
        "High-Margin Procedure Uptake", "No-Show Rate",
        "Conversion Rate", "Collection Efficiency",
        "Contribution Margin", "LTV:CAC Payback", "FCF velocity",
    ]

    NO_SHOW_MAX = 0.03
    CONVERSION_RATE_MIN = 0.65
    COLLECTION_EFFICIENCY_MIN = 0.98
    AR_DAYS_MAX = 35
    BILLING_CAPTURE_LATENCY_HOURS = 24

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []

        ledger = data.get("throughput_ledger", [])
        for rec in ledger:
            if rec.get("procedure_performed") and not rec.get("charge_captured"):
                anomalies.append({
                    "type": "billing_gap",
                    "location_id": rec.get("location_id", "unknown"),
                    "procedure_id": rec.get("procedure_id", "unknown"),
                    "provider_id": rec.get("provider_id", "unknown"),
                    "severity": 0.9,
                })

            ar_days = rec.get("ar_days")
            if ar_days is not None and ar_days > self.AR_DAYS_MAX:
                anomalies.append({
                    "type": "ar_aging",
                    "location_id": rec.get("location_id", "unknown"),
                    "ar_days": ar_days,
                    "threshold": self.AR_DAYS_MAX,
                    "severity": min((ar_days - self.AR_DAYS_MAX) / 30, 1.0),
                })

        capacity = data.get("resource_capacity", [])
        for slot in capacity:
            total_hours = slot.get("total_chair_hours", 0)
            booked_hours = slot.get("booked_chair_hours", 0)
            if total_hours > 0:
                utilization = booked_hours / total_hours
                if utilization < 0.80:
                    anomalies.append({
                        "type": "scheduling_gap",
                        "location_id": slot.get("location_id", "unknown"),
                        "date": slot.get("date", "unknown"),
                        "utilization": utilization,
                        "gap_hours": total_hours - booked_hours,
                        "severity": 1.0 - utilization,
                    })

        variability = data.get("variability_metrics", [])
        for vm in variability:
            no_show = vm.get("no_show_rate")
            if no_show is not None and no_show > self.NO_SHOW_MAX:
                anomalies.append({
                    "type": "no_show_spike",
                    "location_id": vm.get("location_id", "unknown"),
                    "rate": no_show,
                    "threshold": self.NO_SHOW_MAX,
                    "severity": min((no_show - self.NO_SHOW_MAX) / 0.05, 1.0),
                })

            conv_rate = vm.get("conversion_rate")
            if conv_rate is not None and conv_rate < self.CONVERSION_RATE_MIN:
                anomalies.append({
                    "type": "conversion_drop",
                    "location_id": vm.get("location_id", "unknown"),
                    "rate": conv_rate,
                    "threshold": self.CONVERSION_RATE_MIN,
                    "severity": min((self.CONVERSION_RATE_MIN - conv_rate) / 0.20, 1.0),
                })

            coll_eff = vm.get("collection_efficiency")
            if coll_eff is not None and coll_eff < self.COLLECTION_EFFICIENCY_MIN:
                anomalies.append({
                    "type": "collection_drop",
                    "location_id": vm.get("location_id", "unknown"),
                    "efficiency": coll_eff,
                    "threshold": self.COLLECTION_EFFICIENCY_MIN,
                    "severity": min((self.COLLECTION_EFFICIENCY_MIN - coll_eff) / 0.05, 1.0),
                })

        return anomalies

    def derive_intelligence(self, anomalies: List[Dict], data: Dict[str, List[Dict]]) -> List[ActionOutput]:
        actions: List[ActionOutput] = []

        billing_gaps = [a for a in anomalies if a["type"] == "billing_gap"]
        if billing_gaps:
            by_location: Dict[str, List[Dict]] = {}
            for bg in billing_gaps:
                by_location.setdefault(bg["location_id"], []).append(bg)
            for loc_id, gaps in by_location.items():
                roi = len(gaps) * 500
                actions.append(ActionOutput(
                    action=f"CLOSE_BILLING_GAPS:location={loc_id}:count={len(gaps)}",
                    projected_roi=roi,
                    roi_ci=ConfidenceInterval(lower=roi * 0.8, upper=roi * 1.2),
                    validation_plan=f"All {len(gaps)} procedures at {loc_id} must have charges captured within 24h",
                    kill_criteria="Billing gap persists >48h — escalate to CFO and flag for manual audit",
                ))

        sched_gaps = [a for a in anomalies if a["type"] == "scheduling_gap"]
        if sched_gaps:
            top = sorted(sched_gaps, key=lambda x: x["gap_hours"], reverse=True)[:5]
            for sg in top:
                roi = sg["gap_hours"] * 300
                actions.append(ActionOutput(
                    action=(
                        f"OPTIMIZE_SCHEDULE:location={sg['location_id']}:"
                        f"date={sg['date']}:gap_hours={sg['gap_hours']:.1f}"
                    ),
                    projected_roi=roi,
                    roi_ci=ConfidenceInterval(lower=roi * 0.6, upper=roi * 1.4),
                    validation_plan=(
                        f"Utilization at {sg['location_id']} on {sg['date']} "
                        f"must reach >90% after schedule optimization"
                    ),
                    kill_criteria="Utilization still <80% after 2 optimization cycles — flag demand issue to acquisition",
                ))

        no_shows = [a for a in anomalies if a["type"] == "no_show_spike"]
        for ns in sorted(no_shows, key=lambda x: x["severity"], reverse=True)[:3]:
            roi = ns["severity"] * 8_000
            actions.append(ActionOutput(
                action=f"REDUCE_NO_SHOWS:location={ns['location_id']}:rate={ns['rate']:.4f}",
                projected_roi=roi,
                roi_ci=ConfidenceInterval(lower=roi * 0.7, upper=roi * 1.3),
                validation_plan=f"No-show rate at {ns['location_id']} must drop below {self.NO_SHOW_MAX:.0%} within 7 days",
                kill_criteria="Rate unchanged after 14 days of intervention — switch to overbooking strategy",
            ))

        coll_drops = [a for a in anomalies if a["type"] == "collection_drop"]
        for cd in coll_drops:
            roi = cd["severity"] * 12_000
            actions.append(ActionOutput(
                action=f"BOOST_COLLECTIONS:location={cd['location_id']}:efficiency={cd['efficiency']:.4f}",
                projected_roi=roi,
                roi_ci=ConfidenceInterval(lower=roi * 0.6, upper=roi * 1.5),
                validation_plan=(
                    f"Collection efficiency at {cd['location_id']} "
                    f"must reach >{self.COLLECTION_EFFICIENCY_MIN:.0%} within 14 days"
                ),
                kill_criteria="Efficiency still declining after 21 days — escalate to CFO",
            ))

        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for act in actions:
            self.publish(
                event_type="revenue_ops_action",
                payload=act.model_dump(),
            )
            if "CLOSE_BILLING_GAPS" in act.action:
                self.create_task(
                    title=f"Close billing gaps: {act.action.split(':')[1]}",
                    description=act.action,
                    priority=1,
                )
            if "OPTIMIZE_SCHEDULE" in act.action:
                self.create_task(
                    title=f"Schedule optimization: {act.action.split(':')[1]}",
                    description=act.action,
                    priority=2,
                )
            if "BOOST_COLLECTIONS" in act.action:
                self.publish(
                    event_type="collections_alert",
                    payload=act.model_dump(),
                    target="chief-financial-officer",
                )
            logger.info("[%s] emitted: %s", self.role_id, act.action)

    def calculate_leakage(self, ledger: List[Dict]) -> Dict[str, Any]:
        total_procedures = sum(1 for r in ledger if r.get("procedure_performed"))
        captured = sum(1 for r in ledger if r.get("procedure_performed") and r.get("charge_captured"))
        uncaptured = total_procedures - captured
        avg_charge = statistics.mean(
            [r.get("charge_amount", 0) for r in ledger if r.get("charge_amount")]
        ) if any(r.get("charge_amount") for r in ledger) else 0
        return {
            "total_procedures": total_procedures,
            "captured": captured,
            "uncaptured": uncaptured,
            "capture_rate": captured / max(total_procedures, 1),
            "estimated_leakage_dollars": uncaptured * avg_charge,
        }

    def optimize_schedule(self, capacity: List[Dict], demand_signals: List[Dict]) -> List[Dict]:
        recommendations: List[Dict] = []
        for slot in capacity:
            total = slot.get("total_chair_hours", 0)
            booked = slot.get("booked_chair_hours", 0)
            if total > 0 and (booked / total) < 0.90:
                gap = total - booked
                recommendations.append({
                    "location_id": slot.get("location_id"),
                    "date": slot.get("date"),
                    "available_hours": gap,
                    "recommended_action": "backfill_high_margin" if gap > 2 else "extend_hours",
                    "projected_revenue": gap * 250,
                })
        return sorted(recommendations, key=lambda x: x["projected_revenue"], reverse=True)
