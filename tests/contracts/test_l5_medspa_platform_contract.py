from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_SRC = REPO_ROOT / "platform"
if str(PLATFORM_SRC) not in sys.path:
    sys.path.insert(0, str(PLATFORM_SRC))

from l5_medspa_iac.generator import generate_platform_bundle
from l5_medspa_iac.parser import parse_client_spec
from l5_medspa_iac.triage import run_thermo_triage


def test_natural_language_spec_parses_into_platform_model() -> None:
    spec = parse_client_spec(
        """
        Clinic: Luma Medspa
        Services: Botox, Laser resurfacing, Membership
        Staff: 2 injectors, 2 front desk, 1 aesthetician
        Locations: Austin, TX
        Personas: Bridal event patient, High-intent working professional
        Conversion: 26%
        Retention: 79%
        Revenue: $210000
        Compliance: hipaa_safe_messaging, tcpa_opt_out
        """
    )

    assert spec.medspa_name == "Luma Medspa"
    assert len(spec.services) == 3
    assert len(spec.locations) == 1
    assert spec.locations[0].city == "Austin"
    assert spec.locations[0].state == "TX"
    assert spec.kpis.monthly_revenue == 210000.0
    assert "hipaa_safe_messaging" in spec.compliance_rules


def test_thermo_triage_routes_high_entropy_specs() -> None:
    spec = parse_client_spec(
        {
            "medspa_name": "Radiant Fleet Medspa",
            "services": ["Botox", "Laser resurfacing", "Weight loss", "Facial memberships"],
            "staff": ["3 injectors", "4 front desk", "2 aestheticians", "1 medical director"],
            "locations": ["Austin, TX", "Scottsdale, AZ", "Miami, FL"],
            "personas": ["Bridal patient", "Working professional", "Membership patient"],
            "kpis": {"monthly_revenue": 320000, "conversion_rate": 0.24, "retention_rate": 0.8, "show_rate": 0.9, "referral_rate": 0.16},
            "compliance_rules": ["hipaa_safe_messaging", "tcpa_opt_out", "state_specific_recording_disclosure", "medical_director_review", "telemarketing_suppression"],
        }
    )

    triage = run_thermo_triage(spec)
    assert triage.gate_status == "pass"
    assert triage.route == "full_matrix_routing"
    assert triage.shannon_entropy_bits > 2.0


def test_generator_emits_required_artifacts_and_manifest() -> None:
    result = generate_platform_bundle(
        {
            "medspa_name": "Radiant Glow Medspa",
            "services": ["Botox", "Laser resurfacing", "Weight loss"],
            "staff": ["2 injectors", "3 front desk", "1 aesthetician"],
            "locations": ["Austin, TX", "Scottsdale, AZ"],
            "personas": ["Bridal event patient", "High-intent working professional"],
            "kpis": {"monthly_revenue": 175000, "conversion_rate": 0.24, "retention_rate": 0.76, "show_rate": 0.89, "referral_rate": 0.14},
        }
    )

    artifact_paths = {artifact.path for artifact in result.artifacts}
    for marker in [
        "generated/radiant_glow_medspa/ontology_extension.json",
        "generated/radiant_glow_medspa/ontology_shapes.ttl",
        "generated/radiant_glow_medspa/supabase_extension.sql",
        "generated/radiant_glow_medspa/retell_voice_agent.yaml",
        "generated/radiant_glow_medspa/n8n_workflow.json",
        "generated/radiant_glow_medspa/governance_manifest.json",
        "generated/radiant_glow_medspa/docker-compose.yml",
    ]:
        assert marker in artifact_paths


def test_cli_writes_bundle_to_output_directory(tmp_path: Path) -> None:
    spec_path = REPO_ROOT / "platform" / "l5_medspa_iac" / "specs" / "radiant_glow_medspa.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "generate_l5_medspa_platform.py"),
            "--spec-file",
            str(spec_path),
            "--output-dir",
            str(tmp_path),
            "--sandbox-only",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["status"] == "ok"
    assert (tmp_path / "generated" / "radiant_glow_medspa" / "manifest.json").exists()
    assert (tmp_path / "generated" / "radiant_glow_medspa" / "sandbox_snapshot.json").exists()
