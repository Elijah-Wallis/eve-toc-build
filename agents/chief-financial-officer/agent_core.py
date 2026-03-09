"""Chief Financial Officer — Eve L5 Agent."""

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

logger = logging.getLogger("eve.l5.cfo")


class ChiefFinancialOfficer(L5AgentBase):
    role_id: ClassVar[str] = "chief-financial-officer"
    display_name: ClassVar[str] = "Chief Financial Officer"
    cadence_seconds: ClassVar[int] = 120
    poll_tables: ClassVar[List[str]] = [
        "throughput_ledger", "ontology_nodes", "tasks", "outbox",
    ]

    vanity_metrics: ClassVar[List[str]] = [
        "Gross Revenue", "Headcount", "EBITDA (Adj)", "Market Share",
        "R&D Spend",
    ]

    signal_metrics: ClassVar[List[str]] = [
        "FCF velocity", "FCF yield", "Contribution Margin per chair-hour",
        "Contribution Margin per procedure", "Revenue per Chair-Hour",
        "Revenue per Employee", "LTV:CAC ratio", "LTV:CAC payback",
        "AR days", "Fully-loaded cost per employee",
        "Predictive FCF accuracy",
    ]

    VARIANCE_THRESHOLD = 0.005
    AR_DAYS_MAX = 35
    LTV_CAC_MIN = 4.5
    FCF_MAPE_MAX = 0.05
    EBITDA_TARGET = 0.35

    def detect_anomalies(self, data: Dict[str, List[Dict]]) -> List[Dict]:
        anomalies: List[Dict] = []
        ledger = data.get("throughput_ledger", [])

        if ledger:
            revenues = [r.get("revenue", 0) for r in ledger if r.get("revenue") is not None]
            costs = [r.get("cost", 0) for r in ledger if r.get("cost") is not None]

            if len(revenues) >= 2:
                mean_rev = statistics.mean(revenues)
                for i, r in enumerate(revenues):
                    if mean_rev > 0:
                        variance_pct = abs(r - mean_rev) / mean_rev
                        if variance_pct > self.VARIANCE_THRESHOLD:
                            anomalies.append({
                                "type": "revenue_variance",
                                "index": i,
                                "value": r,
                                "expected": mean_rev,
                                "variance_pct": variance_pct,
                                "severity": min(variance_pct / 0.05, 1.0),
                            })

            ar_records = [r for r in ledger if r.get("ar_days") is not None]
            for rec in ar_records:
                if rec["ar_days"] > self.AR_DAYS_MAX:
                    anomalies.append({
                        "type": "ar_aging",
                        "location_id": rec.get("location_id", "unknown"),
                        "ar_days": rec["ar_days"],
                        "threshold": self.AR_DAYS_MAX,
                        "severity": min((rec["ar_days"] - self.AR_DAYS_MAX) / 30, 1.0),
                    })

            for rec in ledger:
                margin = rec.get("contribution_margin")
                expected_margin = rec.get("expected_margin")
                if margin is not None and expected_margin is not None and expected_margin > 0:
                    margin_drop = (expected_margin - margin) / expected_margin
                    if margin_drop > self.VARIANCE_THRESHOLD:
                        anomalies.append({
                            "type": "margin_drop",
                            "location_id": rec.get("location_id", "unknown"),
                            "actual_margin": margin,
                            "expected_margin": expected_margin,
                            "drop_pct": margin_drop,
                            "severity": min(margin_drop / 0.10, 1.0),
                        })

        nodes = data.get("ontology_nodes", [])
        for node in nodes:
            if node.get("entity") == "fcf_forecast":
                mape = node.get("attributes", {}).get("mape", 0)
                if isinstance(mape, (int, float)) and mape > self.FCF_MAPE_MAX:
                    anomalies.append({
                        "type": "fcf_forecast_drift",
                        "node_id": node.get("node_id", "unknown"),
                        "mape": mape,
                        "threshold": self.FCF_MAPE_MAX,
                        "severity": min((mape - self.FCF_MAPE_MAX) / 0.05, 1.0),
                    })

        return anomalies

    def derive_intelligence(self, anomalies: List[Dict], data: Dict[str, List[Dict]]) -> List[ActionOutput]:
        actions: List[ActionOutput] = []

        rev_variances = [a for a in anomalies if a["type"] == "revenue_variance"]
        if rev_variances:
            top = sorted(rev_variances, key=lambda x: x["severity"], reverse=True)[:5]
            for rv in top:
                roi = rv["severity"] * 15_000
                actions.append(ActionOutput(
                    action=(
                        f"DECOMPOSE_VARIANCE:revenue:"
                        f"variance_pct={rv['variance_pct']:.4f}:"
                        f"factors=volume,mix,price,cost"
                    ),
                    projected_roi=roi,
                    roi_ci=ConfidenceInterval(lower=roi * 0.6, upper=roi * 1.4),
                    validation_plan=(
                        "Run volume/mix/price/cost decomposition; "
                        "identify dominant factor within 1 tick; "
                        "publish root cause to hive"
                    ),
                    kill_criteria="Variance self-corrects below 0.5% within 3 ticks",
                ))

        ar_anomalies = [a for a in anomalies if a["type"] == "ar_aging"]
        for ar in sorted(ar_anomalies, key=lambda x: x["severity"], reverse=True)[:3]:
            roi = ar["severity"] * 20_000
            actions.append(ActionOutput(
                action=(
                    f"ACCELERATE_COLLECTIONS:location={ar['location_id']}:"
                    f"current_ar_days={ar['ar_days']}"
                ),
                projected_roi=roi,
                roi_ci=ConfidenceInterval(lower=roi * 0.7, upper=roi * 1.3),
                validation_plan=f"AR days for {ar['location_id']} must drop below {self.AR_DAYS_MAX} within 14 calendar days",
                kill_criteria=f"AR days still >{self.AR_DAYS_MAX + 10} after 30 days — escalate to revenue ops",
            ))

        margin_drops = [a for a in anomalies if a["type"] == "margin_drop"]
        for md in sorted(margin_drops, key=lambda x: x["severity"], reverse=True)[:3]:
            roi = md["severity"] * 25_000
            actions.append(ActionOutput(
                action=(
                    f"MARGIN_RECOVERY:location={md['location_id']}:"
                    f"drop={md['drop_pct']:.4f}:"
                    f"actual={md['actual_margin']:.4f}"
                ),
                projected_roi=roi,
                roi_ci=ConfidenceInterval(lower=roi * 0.5, upper=roi * 1.5),
                validation_plan=(
                    f"Contribution margin at {md['location_id']} must recover to "
                    f">={md['expected_margin']:.4f} within 7 days"
                ),
                kill_criteria="Margin continues declining after 2 intervention cycles — trigger cost audit",
            ))

        fcf_drifts = [a for a in anomalies if a["type"] == "fcf_forecast_drift"]
        for fd in fcf_drifts:
            actions.append(ActionOutput(
                action=f"RECALIBRATE_FCF_MODEL:node={fd['node_id']}:mape={fd['mape']:.4f}",
                projected_roi=30_000,
                roi_ci=ConfidenceInterval(lower=15_000, upper=50_000),
                validation_plan=f"MAPE must drop below {self.FCF_MAPE_MAX:.2%} within 7 days",
                kill_criteria="MAPE still above 10% after 3 recalibrations — rebuild model from scratch",
            ))

        return actions

    def emit_actions(self, actions: List[ActionOutput]) -> None:
        for act in actions:
            self.publish(
                event_type="financial_action",
                payload=act.model_dump(),
            )
            if "ACCELERATE_COLLECTIONS" in act.action:
                self.publish(
                    event_type="collections_alert",
                    payload=act.model_dump(),
                    target="head-revenue-operations",
                )
            if "MARGIN_RECOVERY" in act.action:
                self.create_task(
                    title=f"Margin recovery: {act.action.split(':')[1]}",
                    description=act.action,
                    priority=1,
                )
            logger.info("[%s] emitted: %s", self.role_id, act.action)

    def decompose_variance(
        self, actual: float, expected: float, volume: float, mix: float, price: float, cost: float,
    ) -> Dict[str, float]:
        total_var = actual - expected
        if abs(total_var) < 1e-9:
            return {"volume": 0, "mix": 0, "price": 0, "cost": 0, "total": 0}
        factor_sum = abs(volume) + abs(mix) + abs(price) + abs(cost)
        if factor_sum < 1e-9:
            return {"volume": 0, "mix": 0, "price": 0, "cost": 0, "total": total_var}
        return {
            "volume": total_var * (abs(volume) / factor_sum),
            "mix": total_var * (abs(mix) / factor_sum),
            "price": total_var * (abs(price) / factor_sum),
            "cost": total_var * (abs(cost) / factor_sum),
            "total": total_var,
        }

    def project_fcf(self, ledger: List[Dict], horizon_days: int = 90) -> Dict[str, Any]:
        cash_flows = [r.get("net_cash_flow", 0) for r in ledger if r.get("net_cash_flow") is not None]
        if not cash_flows:
            return {"projected_fcf": 0, "confidence": 0, "horizon_days": horizon_days}
        avg_daily = statistics.mean(cash_flows)
        std_daily = statistics.stdev(cash_flows) if len(cash_flows) > 1 else avg_daily * 0.1
        projected = avg_daily * horizon_days
        return {
            "projected_fcf": projected,
            "ci_lower": (avg_daily - 1.96 * std_daily) * horizon_days,
            "ci_upper": (avg_daily + 1.96 * std_daily) * horizon_days,
            "confidence": 0.95,
            "horizon_days": horizon_days,
        }
