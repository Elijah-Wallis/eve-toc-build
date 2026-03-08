from __future__ import annotations

import json
import re
from typing import Any
from typing import Dict
from typing import Iterable
from typing import List

from .models import BrandingSpec
from .models import GovernanceSpec
from .models import KpiTargets
from .models import LocationSpec
from .models import MedspaClientSpec
from .models import PersonaSpec
from .models import ServiceSpec
from .models import StaffRoleSpec
from .models import slugify


def _split_csv(value: str) -> List[str]:
    return [part.strip() for part in re.split(r"[,\n;|]+", value) if part.strip()]


def _split_locations(value: str) -> List[str]:
    parts = [part.strip() for part in re.split(r"[;\n|]+", value) if part.strip()]
    return parts if parts else [value.strip()]


def _extract_percent(value: str, default: float) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*%?", value)
    if not match:
        return default
    number = float(match.group(1))
    return number / 100.0 if number > 1 else number


def _extract_money(value: str, default: float) -> float:
    match = re.search(r"(\d[\d,]*(?:\.\d+)?)", value.replace("$", ""))
    if not match:
        return default
    return float(match.group(1).replace(",", ""))


def _make_services(service_names: Iterable[str]) -> List[ServiceSpec]:
    services: List[ServiceSpec] = []
    for name in service_names:
        lowered = name.lower()
        compliance_tags: List[str] = []
        category = "core"
        avg_ticket = 450.0
        duration = 60

        if any(token in lowered for token in ["botox", "filler", "injectable"]):
            category = "injectables"
            avg_ticket = 650.0
            duration = 45
        elif any(token in lowered for token in ["laser", "rf", "morpheus", "resurfacing"]):
            category = "energy_based"
            avg_ticket = 1100.0
            duration = 75
        elif any(token in lowered for token in ["weight", "semaglutide", "glp"]):
            category = "medical_weight_loss"
            avg_ticket = 950.0
            duration = 40
            compliance_tags.append("medical_director_review")
        elif any(token in lowered for token in ["facial", "hydrafacial", "skin"]):
            category = "skin_health"
            avg_ticket = 300.0
            duration = 50

        if any(token in lowered for token in ["iv", "hormone", "medical"]):
            compliance_tags.append("licensed_provider_required")

        services.append(
            ServiceSpec(
                name=name,
                category=category,
                avg_ticket=avg_ticket,
                duration_minutes=duration,
                compliance_tags=compliance_tags,
            )
        )
    return services


def _make_staff(entries: Iterable[str]) -> List[StaffRoleSpec]:
    roles: List[StaffRoleSpec] = []
    for entry in entries:
        match = re.match(r"(?P<count>\d+)\s*x?\s*(?P<role>.+)", entry.strip(), flags=re.IGNORECASE)
        if match:
            count = int(match.group("count"))
            role_name = match.group("role").strip()
        else:
            count = 1
            role_name = entry.strip()

        lowered = role_name.lower()
        skills = []
        licenses = []
        if "injector" in lowered or "nurse" in lowered:
            skills.extend(["injectables", "patient_assessment"])
            licenses.append("rn_or_np")
        if "front desk" in lowered or "concierge" in lowered:
            skills.extend(["lead_intake", "booking", "retention"])
        if "aesthetician" in lowered:
            skills.extend(["skin_consults", "upsell"])

        roles.append(StaffRoleSpec(role=role_name, count=count, skills=skills, licenses=licenses))
    return roles


def _default_personas(service_names: List[str]) -> List[PersonaSpec]:
    concerns = [service.lower() for service in service_names[:3]] or ["skin quality", "confidence"]
    return [
        PersonaSpec(
            name="High-intent working professional",
            age_band="30-50",
            concerns=concerns,
            channels=["voice", "sms", "email"],
            urgency_bias=0.84,
        ),
        PersonaSpec(
            name="Referral-driven maintenance patient",
            age_band="35-60",
            concerns=concerns[:2] or ["anti-aging"],
            channels=["sms", "email"],
            urgency_bias=0.58,
        ),
    ]


def spec_from_dict(payload: Dict[str, Any]) -> MedspaClientSpec:
    medspa_name = payload.get("medspa_name") or payload.get("clinic_name") or payload.get("brand") or "EVE Medspa Client"
    client_id = payload.get("client_id") or slugify(medspa_name)

    service_payload = payload.get("services") or []
    if service_payload and isinstance(service_payload[0], dict):
        services = [ServiceSpec(**service) for service in service_payload]
    else:
        services = _make_services(service_payload or ["Botox", "Laser resurfacing", "Memberships"])

    staff_payload = payload.get("staff") or payload.get("staff_roles") or []
    if staff_payload and isinstance(staff_payload[0], dict):
        staff = [StaffRoleSpec(**role) for role in staff_payload]
    else:
        staff = _make_staff(staff_payload or ["2 injectors", "3 front desk", "1 aesthetician"])

    location_payload = payload.get("locations") or []
    locations = []
    for item in location_payload:
        if isinstance(item, dict):
            locations.append(LocationSpec(**item))
        else:
            parts = [part.strip() for part in str(item).split(",")]
            city = parts[0] if parts else "Austin"
            state = parts[1] if len(parts) > 1 else "TX"
            locations.append(LocationSpec(city=city, state=state))
    if not locations:
        locations = [LocationSpec(city="Austin", state="TX", compliance_rules=["tcpa", "two_party_consent_review"])]

    persona_payload = payload.get("personas") or []
    if persona_payload and isinstance(persona_payload[0], dict):
        personas = [PersonaSpec(**persona) for persona in persona_payload]
    elif persona_payload:
        personas = [PersonaSpec(name=name, concerns=[service.name for service in services[:2]]) for name in persona_payload]
    else:
        personas = _default_personas([service.name for service in services])

    branding_payload = payload.get("branding") or {}
    branding = BrandingSpec(**branding_payload) if isinstance(branding_payload, dict) else BrandingSpec()

    governance_payload = payload.get("governance") or {}
    governance = GovernanceSpec(**governance_payload) if isinstance(governance_payload, dict) else GovernanceSpec()

    kpi_payload = payload.get("kpis") or {}
    kpis = KpiTargets(
        conversion_rate=float(kpi_payload.get("conversion_rate", 0.24)),
        retention_rate=float(kpi_payload.get("retention_rate", 0.76)),
        monthly_revenue=float(kpi_payload.get("monthly_revenue", 175000.0)),
        show_rate=float(kpi_payload.get("show_rate", 0.89)),
        referral_rate=float(kpi_payload.get("referral_rate", 0.14)),
    )

    compliance_rules = list(
        payload.get("compliance_rules")
        or payload.get("rules")
        or ["hipaa_safe_messaging", "tcpa_opt_out", "state_specific_recording_disclosure"]
    )

    return MedspaClientSpec(
        client_id=client_id,
        medspa_name=medspa_name,
        services=services,
        staff=staff,
        locations=locations,
        personas=personas,
        kpis=kpis,
        branding=branding,
        compliance_rules=compliance_rules,
        governance=governance,
        channels=list(payload.get("channels") or ["voice", "sms", "email", "telegram"]),
        notes=list(payload.get("notes") or []),
    )


def spec_from_natural_language(text: str) -> MedspaClientSpec:
    normalized = text.strip()
    lines = [line.strip("- ").strip() for line in normalized.splitlines() if line.strip()]
    fields: Dict[str, str] = {}

    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip().lower()] = value.strip()

    medspa_name = (
        fields.get("medspa")
        or fields.get("clinic")
        or fields.get("brand")
        or fields.get("client")
        or "EVE Prototype Medspa"
    )
    services = _split_csv(fields.get("services", "Botox, Laser resurfacing, Membership"))
    staff = _split_csv(fields.get("staff", "2 injectors, 2 front desk, 1 aesthetician"))
    personas = _split_csv(fields.get("personas", "High-intent working professional, Bridal event patient"))
    locations = _split_locations(fields.get("locations", "Austin, TX"))
    compliance_rules = _split_csv(
        fields.get(
            "compliance",
            fields.get("rules", "hipaa_safe_messaging, tcpa_opt_out, state_specific_recording_disclosure"),
        )
    )
    palette = _split_csv(fields.get("palette", "#0D9488, #111827, #F59E0B"))
    tone_keywords = _split_csv(fields.get("tone", "clinical, luxury, resilient"))
    differentiators = _split_csv(fields.get("branding", "High-touch concierge, board-certified, outcomes-led"))

    conversion_line = fields.get("conversion", "24%")
    retention_line = fields.get("retention", "76%")
    revenue_line = fields.get("revenue", "$175000")
    show_rate_line = fields.get("show_rate", fields.get("show", "89%"))
    referral_line = fields.get("referral_rate", "14%")

    location_specs: List[LocationSpec] = []
    for entry in locations:
        parts = [part.strip() for part in entry.split(",")]
        city = parts[0] if parts else "Austin"
        state = parts[1] if len(parts) > 1 else "TX"
        location_specs.append(
            LocationSpec(
                city=city,
                state=state,
                compliance_rules=list(compliance_rules),
            )
        )

    return MedspaClientSpec(
        client_id=slugify(medspa_name),
        medspa_name=medspa_name,
        services=_make_services(services),
        staff=_make_staff(staff),
        locations=location_specs,
        personas=[
            PersonaSpec(name=name, concerns=[service.name for service in _make_services(services)[:2]], channels=["voice", "sms", "email"], urgency_bias=0.72)
            for name in personas
        ],
        kpis=KpiTargets(
            conversion_rate=_extract_percent(conversion_line, 0.24),
            retention_rate=_extract_percent(retention_line, 0.76),
            monthly_revenue=_extract_money(revenue_line, 175000.0),
            show_rate=_extract_percent(show_rate_line, 0.89),
            referral_rate=_extract_percent(referral_line, 0.14),
        ),
        branding=BrandingSpec(
            palette=palette,
            differentiators=differentiators,
            tone_keywords=tone_keywords,
        ),
        compliance_rules=compliance_rules,
        governance=GovernanceSpec(),
        channels=_split_csv(fields.get("channels", "voice, sms, email, telegram")),
        notes=_split_csv(fields.get("notes", "")),
    )


def parse_client_spec(source: str | Dict[str, Any]) -> MedspaClientSpec:
    if isinstance(source, dict):
        return spec_from_dict(source)

    candidate = source.strip()
    if not candidate:
        raise ValueError("Client spec source is empty")

    if candidate.startswith("{"):
        return spec_from_dict(json.loads(candidate))

    return spec_from_natural_language(candidate)
