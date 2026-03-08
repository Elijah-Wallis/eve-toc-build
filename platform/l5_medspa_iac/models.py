from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Dict
from typing import List


def slugify(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace("&", " and ")
        .replace("/", " ")
        .replace("-", " ")
        .replace("__", "_")
        .replace("  ", " ")
        .replace(" ", "_")
    )


@dataclass
class BrandingSpec:
    voice: str = "authoritative_empathic"
    palette: List[str] = field(default_factory=lambda: ["#0D9488", "#111827", "#F59E0B"])
    differentiators: List[str] = field(default_factory=list)
    tone_keywords: List[str] = field(default_factory=lambda: ["clinical", "luxury", "reassuring"])

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ServiceSpec:
    name: str
    category: str = "core"
    avg_ticket: float = 0.0
    duration_minutes: int = 60
    compliance_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StaffRoleSpec:
    role: str
    count: int = 1
    skills: List[str] = field(default_factory=list)
    licenses: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LocationSpec:
    city: str
    state: str
    timezone: str = "America/Chicago"
    compliance_rules: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PersonaSpec:
    name: str
    age_band: str = "30-55"
    concerns: List[str] = field(default_factory=list)
    channels: List[str] = field(default_factory=lambda: ["voice", "sms", "email"])
    urgency_bias: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KpiTargets:
    conversion_rate: float = 0.22
    retention_rate: float = 0.72
    monthly_revenue: float = 150000.0
    show_rate: float = 0.86
    referral_rate: float = 0.12

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GovernanceSpec:
    immutable_telemetry: bool = True
    elijah_review_loop: bool = True
    acceptance_suite: List[str] = field(
        default_factory=lambda: [
            "bash scripts/acceptance/run_contract_suite.sh",
            "python3 scripts/ops/emit_telemetry_probe.py",
            "python3 scripts/ops/verify_immutable_telemetry.py --require-signed --allow-legacy-interleaving",
        ]
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MedspaClientSpec:
    client_id: str
    medspa_name: str
    services: List[ServiceSpec]
    staff: List[StaffRoleSpec]
    locations: List[LocationSpec]
    personas: List[PersonaSpec]
    kpis: KpiTargets
    branding: BrandingSpec = field(default_factory=BrandingSpec)
    compliance_rules: List[str] = field(default_factory=list)
    governance: GovernanceSpec = field(default_factory=GovernanceSpec)
    channels: List[str] = field(default_factory=lambda: ["voice", "sms", "email", "telegram"])
    notes: List[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return slugify(self.client_id or self.medspa_name)

    @property
    def primary_location(self) -> LocationSpec:
        return self.locations[0]

    def service_names(self) -> List[str]:
        return [service.name for service in self.services]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "client_id": self.client_id,
            "medspa_name": self.medspa_name,
            "services": [service.to_dict() for service in self.services],
            "staff": [role.to_dict() for role in self.staff],
            "locations": [location.to_dict() for location in self.locations],
            "personas": [persona.to_dict() for persona in self.personas],
            "kpis": self.kpis.to_dict(),
            "branding": self.branding.to_dict(),
            "compliance_rules": list(self.compliance_rules),
            "governance": self.governance.to_dict(),
            "channels": list(self.channels),
            "notes": list(self.notes),
        }


@dataclass
class ThermoTriageDecision:
    gate_status: str
    route: str
    tier: str
    shannon_entropy_bits: float
    leverage_score: float
    friction_score: float
    pareto_priority: float
    least_action_path: List[str]
    rationale: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InterventionPlan:
    name: str
    efficacy: float
    friction: float
    complexity_reduction: float
    impact_vector: Dict[str, float]
    selected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OptimizationResult:
    triage: ThermoTriageDecision
    selected_interventions: List[InterventionPlan]
    pareto_frontier: List[InterventionPlan]
    forecast: Dict[str, float]
    bottlenecks: List[str]
    journey_graph: Dict[str, Any]
    skill_embedding_distances: Dict[str, Dict[str, float]]
    solver_summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "triage": self.triage.to_dict(),
            "selected_interventions": [item.to_dict() for item in self.selected_interventions],
            "pareto_frontier": [item.to_dict() for item in self.pareto_frontier],
            "forecast": dict(self.forecast),
            "bottlenecks": list(self.bottlenecks),
            "journey_graph": dict(self.journey_graph),
            "skill_embedding_distances": {
                name: dict(values) for name, values in self.skill_embedding_distances.items()
            },
            "solver_summary": dict(self.solver_summary),
        }


@dataclass
class GeneratedArtifact:
    path: str
    content: str
    kind: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlatformGenerationResult:
    spec: MedspaClientSpec
    optimization: OptimizationResult
    artifacts: List[GeneratedArtifact]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "optimization": self.optimization.to_dict(),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }
