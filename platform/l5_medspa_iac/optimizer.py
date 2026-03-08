from __future__ import annotations

import math
from itertools import combinations
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

from .models import InterventionPlan
from .models import MedspaClientSpec
from .models import OptimizationResult
from .triage import run_thermo_triage

try:  # Optional scientific/graph stack for richer sandbox behavior.
    import networkx as nx  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    nx = None

try:  # Optional linear-programming solver.
    import pulp  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pulp = None

try:  # Optional vector distance helper.
    from scipy.spatial.distance import cosine  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    cosine = None


def _candidate_interventions(spec: MedspaClientSpec) -> List[InterventionPlan]:
    return [
        InterventionPlan(
            name="Voice lead capture lattice",
            efficacy=0.92,
            friction=0.34,
            complexity_reduction=0.48,
            impact_vector={"conversion": 0.17, "retention": 0.04, "revenue": 0.16, "compliance": 0.06},
        ),
        InterventionPlan(
            name="Smart intake + tier routing",
            efficacy=0.83,
            friction=0.29,
            complexity_reduction=0.42,
            impact_vector={"conversion": 0.11, "retention": 0.05, "revenue": 0.09, "compliance": 0.12},
        ),
        InterventionPlan(
            name="Recall and nurture orchestration",
            efficacy=0.78,
            friction=0.25,
            complexity_reduction=0.31,
            impact_vector={"conversion": 0.06, "retention": 0.18, "revenue": 0.1, "compliance": 0.03},
        ),
        InterventionPlan(
            name="Telemetry + Elijah_EveBot governance",
            efficacy=0.72,
            friction=0.19,
            complexity_reduction=0.27,
            impact_vector={"conversion": 0.03, "retention": 0.04, "revenue": 0.05, "compliance": 0.22},
        ),
        InterventionPlan(
            name="Persona-tuned upsell graph",
            efficacy=0.76,
            friction=0.28,
            complexity_reduction=0.24,
            impact_vector={"conversion": 0.08, "retention": 0.09, "revenue": 0.14, "compliance": 0.02},
        ),
        InterventionPlan(
            name="Least-action scheduler optimizer",
            efficacy=0.81,
            friction=0.24,
            complexity_reduction=0.39,
            impact_vector={"conversion": 0.09, "retention": 0.06, "revenue": 0.12, "compliance": 0.05},
        ),
    ]


def _weighted_value(spec: MedspaClientSpec, intervention: InterventionPlan) -> float:
    weights = {
        "conversion": 0.33,
        "retention": 0.22,
        "revenue": 0.31,
        "compliance": 0.14,
    }
    return sum(weights[key] * intervention.impact_vector.get(key, 0.0) for key in weights)


def _pareto_frontier(interventions: List[InterventionPlan]) -> List[InterventionPlan]:
    frontier: List[InterventionPlan] = []
    for candidate in interventions:
        dominated = False
        for other in interventions:
            if other is candidate:
                continue
            if (
                other.efficacy >= candidate.efficacy
                and other.complexity_reduction >= candidate.complexity_reduction
                and other.friction <= candidate.friction
                and (
                    other.efficacy > candidate.efficacy
                    or other.complexity_reduction > candidate.complexity_reduction
                    or other.friction < candidate.friction
                )
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return sorted(frontier, key=lambda item: (_weighted_value_for_sort(item), -item.friction), reverse=True)


def _weighted_value_for_sort(intervention: InterventionPlan) -> float:
    return intervention.efficacy + intervention.complexity_reduction - intervention.friction


def _select_interventions(
    spec: MedspaClientSpec, interventions: List[InterventionPlan]
) -> Tuple[List[InterventionPlan], Dict[str, Any]]:
    budget = 1.15 + (len(spec.staff) * 0.08)
    solver_used = "heuristic_greedy"

    if pulp is not None:  # pragma: no cover - depends on optional solver
        solver_used = "pulp"
        problem = pulp.LpProblem("l5_medspa_iac", pulp.LpMaximize)
        decision_vars = {
            intervention.name: pulp.LpVariable(intervention.name.replace(" ", "_"), cat="Binary")
            for intervention in interventions
        }
        problem += pulp.lpSum(
            (
                (_weighted_value(spec, intervention) + intervention.complexity_reduction * 0.3)
                / max(intervention.friction, 0.05)
            )
            * decision_vars[intervention.name]
            for intervention in interventions
        )
        problem += pulp.lpSum(
            intervention.friction * decision_vars[intervention.name] for intervention in interventions
        ) <= budget
        problem += pulp.lpSum(decision_vars.values()) >= 2
        problem.solve(pulp.PULP_CBC_CMD(msg=False))
        selected = []
        for intervention in interventions:
            intervention.selected = bool(decision_vars[intervention.name].value())
            if intervention.selected:
                selected.append(intervention)
        return selected, {"solver": solver_used, "budget": budget}

    ranked = sorted(
        interventions,
        key=lambda item: ((_weighted_value(spec, item) + item.complexity_reduction * 0.3) / item.friction),
        reverse=True,
    )
    selected: List[InterventionPlan] = []
    spent = 0.0
    for item in ranked:
        if spent + item.friction <= budget or len(selected) < 2:
            item.selected = True
            selected.append(item)
            spent += item.friction
    return selected, {"solver": solver_used, "budget": budget, "spent": round(spent, 3)}


def _cosine_distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = sorted(set(a) | set(b))
    va = [a.get(key, 0.0) for key in keys]
    vb = [b.get(key, 0.0) for key in keys]
    if cosine is not None:  # pragma: no cover - optional dependency
        return float(cosine(va, vb))
    dot = sum(x * y for x, y in zip(va, vb))
    norm_a = math.sqrt(sum(x * x for x in va))
    norm_b = math.sqrt(sum(y * y for y in vb))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return 1.0 - (dot / (norm_a * norm_b))


def _skill_embedding_distances(interventions: List[InterventionPlan]) -> Dict[str, Dict[str, float]]:
    distances: Dict[str, Dict[str, float]] = {}
    for left, right in combinations(interventions, 2):
        distance = round(_cosine_distance(left.impact_vector, right.impact_vector), 4)
        distances.setdefault(left.name, {})[right.name] = distance
        distances.setdefault(right.name, {})[left.name] = distance
    return distances


def _build_journey_graph(spec: MedspaClientSpec, selected: List[InterventionPlan]) -> Dict[str, Any]:
    nodes = [
        "lead_capture",
        "thermo_triage",
        "qualification",
        "booking",
        "show",
        "retention",
        "referral",
    ]
    edges = [
        ("lead_capture", "thermo_triage", 0.08),
        ("thermo_triage", "qualification", 0.12),
        ("qualification", "booking", 0.18),
        ("booking", "show", 0.16),
        ("show", "retention", 0.13),
        ("retention", "referral", 0.09),
    ]
    friction_discount = sum(item.complexity_reduction for item in selected) * 0.03
    weighted_edges = [
        {"from": left, "to": right, "friction": round(max(0.03, weight - friction_discount), 3)}
        for left, right, weight in edges
    ]

    if nx is not None:  # pragma: no cover - optional dependency
        graph = nx.DiGraph()
        for edge in weighted_edges:
            graph.add_edge(edge["from"], edge["to"], weight=edge["friction"])
        shortest = nx.shortest_path(
            graph, source="lead_capture", target="referral", weight="weight"
        )
    else:
        shortest = nodes

    return {
        "nodes": nodes,
        "edges": weighted_edges,
        "least_action_path": shortest,
        "tooling": {
            "networkx_enabled": nx is not None,
            "pulp_enabled": pulp is not None,
            "scipy_enabled": cosine is not None,
        },
    }


def _forecast(spec: MedspaClientSpec, selected: List[InterventionPlan]) -> Dict[str, float]:
    conversion_gain = sum(item.impact_vector["conversion"] for item in selected)
    retention_gain = sum(item.impact_vector["retention"] for item in selected)
    revenue_gain = sum(item.impact_vector["revenue"] for item in selected)
    show_gain = sum(item.impact_vector["compliance"] for item in selected) * 0.25

    baseline_conversion = max(0.08, spec.kpis.conversion_rate * 0.78)
    baseline_retention = max(0.40, spec.kpis.retention_rate * 0.84)
    baseline_revenue = spec.kpis.monthly_revenue * 0.88
    baseline_show = max(0.65, spec.kpis.show_rate * 0.92)

    forecast_conversion = min(0.92, baseline_conversion + conversion_gain)
    forecast_retention = min(0.95, baseline_retention + retention_gain)
    forecast_show = min(0.98, baseline_show + show_gain)
    forecast_revenue = baseline_revenue * (1.0 + revenue_gain + conversion_gain * 0.6)

    return {
        "baseline_conversion_rate": round(baseline_conversion, 4),
        "projected_conversion_rate": round(forecast_conversion, 4),
        "baseline_retention_rate": round(baseline_retention, 4),
        "projected_retention_rate": round(forecast_retention, 4),
        "baseline_show_rate": round(baseline_show, 4),
        "projected_show_rate": round(forecast_show, 4),
        "baseline_monthly_revenue": round(baseline_revenue, 2),
        "projected_monthly_revenue": round(forecast_revenue, 2),
        "projected_annual_revenue": round(forecast_revenue * 12, 2),
    }


def _bottlenecks(spec: MedspaClientSpec, selected: List[InterventionPlan]) -> List[str]:
    selected_names = {item.name for item in selected}
    bottlenecks = [
        "High-intent leads decay outside staffed hours, creating avoidable Shannon entropy in the intake queue.",
        "Manual qualification spreads work across too many hands, increasing thermodynamic friction and callback latency.",
        "Service-persona matching is implicit instead of encoded, which weakens upsell and retention loops.",
    ]
    if "Telemetry + Elijah_EveBot governance" not in selected_names:
        bottlenecks.append("Governance coverage is underpowered without immutable telemetry and proactive review loops.")
    if len(spec.locations) > 1:
        bottlenecks.append("Multi-location routing needs explicit compliance and timezone partitioning to avoid cross-site drift.")
    return bottlenecks


def run_platform_optimization(spec: MedspaClientSpec) -> OptimizationResult:
    triage = run_thermo_triage(spec)
    interventions = _candidate_interventions(spec)
    pareto = _pareto_frontier(interventions)
    selected, solver_summary = _select_interventions(spec, interventions)
    graph = _build_journey_graph(spec, selected)
    forecast = _forecast(spec, selected)
    distances = _skill_embedding_distances(interventions)
    solver_summary["complexity_reduction"] = round(
        sum(item.complexity_reduction for item in selected), 3
    )
    solver_summary["least_action_path"] = graph["least_action_path"]

    return OptimizationResult(
        triage=triage,
        selected_interventions=selected,
        pareto_frontier=pareto,
        forecast=forecast,
        bottlenecks=_bottlenecks(spec, selected),
        journey_graph=graph,
        skill_embedding_distances=distances,
        solver_summary=solver_summary,
    )
