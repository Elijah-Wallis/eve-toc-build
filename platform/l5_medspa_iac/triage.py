from __future__ import annotations

import math
from typing import List

from .models import MedspaClientSpec
from .models import ThermoTriageDecision


def _shannon_entropy(counts: List[int]) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    entropy = 0.0
    for count in counts:
        if count <= 0:
            continue
        probability = count / total
        entropy -= probability * math.log(probability, 2)
    return entropy


def _missing_hard_system_fields(spec: MedspaClientSpec) -> List[str]:
    missing = []
    if not spec.services:
        missing.append("services")
    if not spec.staff:
        missing.append("staff")
    if not spec.locations:
        missing.append("locations")
    if spec.kpis.monthly_revenue <= 0:
        missing.append("kpis.monthly_revenue")
    return missing


def run_thermo_triage(spec: MedspaClientSpec) -> ThermoTriageDecision:
    missing = _missing_hard_system_fields(spec)
    counts = [
        len(spec.services),
        len(spec.staff),
        len(spec.locations),
        len(spec.personas),
        len(spec.channels),
        len(spec.compliance_rules),
    ]
    entropy_bits = round(_shannon_entropy(counts), 3)

    revenue_weight = min(1.0, spec.kpis.monthly_revenue / 250000.0)
    leverage_score = round(
        min(
            0.99,
            0.18
            + (len(spec.services) * 0.06)
            + (len(spec.personas) * 0.05)
            + (spec.kpis.conversion_rate * 0.55)
            + (revenue_weight * 0.22),
        ),
        3,
    )
    friction_score = round(
        0.18
        + (len(spec.locations) * 0.12)
        + (len(spec.compliance_rules) * 0.06)
        + (max(len(spec.staff) - 3, 0) * 0.04),
        3,
    )
    pareto_priority = round(max(0.05, leverage_score / max(friction_score, 0.1)), 3)

    if missing:
        return ThermoTriageDecision(
            gate_status="halt_acquire",
            route="tier_1",
            tier="tier_1",
            shannon_entropy_bits=entropy_bits,
            leverage_score=leverage_score,
            friction_score=friction_score,
            pareto_priority=pareto_priority,
            least_action_path=["acquire_minimum_viable_data", "re-run_thermo_triage"],
            rationale=[
                "Hard-system minimum viable data is incomplete.",
                f"Missing fields: {', '.join(missing)}.",
                "No ontology or IaC projection should be emitted until the spec clears the Thermo_Triage gate.",
            ],
        )

    if entropy_bits >= 2.15 or len(spec.locations) > 2 or len(spec.compliance_rules) > 4:
        route = "full_matrix_routing"
        tier = "tier_2"
    elif entropy_bits >= 1.45 or leverage_score >= 0.72:
        route = "tier_2_routing"
        tier = "tier_2"
    else:
        route = "tier_1_routing"
        tier = "tier_1"

    least_action_path = [
        "parse_spec",
        "score_leverage_and_entropy",
        "project_ontology_and_schema",
        "generate_voice_and_workflows",
        "run_sandbox_and_acceptance_gates",
        "emit_iac_bundle",
    ]
    rationale = [
        f"Shannon entropy bound is {entropy_bits} bits across services, personas, channels, locations, and compliance surfaces.",
        f"Leverage score is {leverage_score} and friction score is {friction_score}, optimizing for Max_Efficacy | Min_Friction | Bio_Opt.",
        f"Pareto priority is {pareto_priority}; route selected is {route}.",
    ]
    if route == "full_matrix_routing":
        rationale.append(
            "High-entropy task profile triggers full_matrix_routing so cross-domain ontology, voice, workflow, compliance, and KPI surfaces co-optimize together."
        )
    elif route == "tier_2_routing":
        rationale.append(
            "Moderate entropy with high leverage favors tier_2_routing to preserve agility while still activating guardrails and multi-surface synthesis."
        )
    else:
        rationale.append(
            "Low-friction spec can take the tier_1_routing least-action path with deterministic projections and narrow review loops."
        )

    return ThermoTriageDecision(
        gate_status="pass",
        route=route,
        tier=tier,
        shannon_entropy_bits=entropy_bits,
        leverage_score=leverage_score,
        friction_score=friction_score,
        pareto_priority=pareto_priority,
        least_action_path=least_action_path,
        rationale=rationale,
    )
