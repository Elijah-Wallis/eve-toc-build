# EVE L5_Medspa_IaC Platform Layer Prototype

This package turns a declarative Medspa client spec into a platform bundle:

- ontology extension + SHACL shapes
- Supabase schema projection
- Retell / voice-agent orchestration config
- n8n + Telegram ingress workflow stubs
- digital-twin simulator snapshot
- governance + IaC scaffolding

## Quick start

```bash
python3 scripts/generate_l5_medspa_platform.py \
  --spec-file platform/l5_medspa_iac/specs/radiant_glow_medspa.json \
  --output-dir /tmp/eve-platform
```

Or parse natural language:

```bash
python3 scripts/generate_l5_medspa_platform.py \
  --spec-text "Clinic: Radiant Glow Medspa
services: Botox, Laser resurfacing, Membership
staff: 2 injectors, 3 front desk, 1 aesthetician
locations: Austin, TX
personas: Bridal event patient, High-intent working professional
conversion: 24%
retention: 76%
revenue: $175000
branding: clinical luxury, concierge follow-through" \
  --output-dir /tmp/eve-platform
```

## Optional optimization stack

The optimizer uses `networkx`, `PuLP`, and `scipy` when available, with deterministic
fallbacks when they are not installed. See `requirements.txt`.

For cloud-like environments without those packages preloaded:

```bash
bash scripts/setup_cloud_python_scientific_stack.sh
```
