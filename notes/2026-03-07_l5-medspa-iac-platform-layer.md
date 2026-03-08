# 2026-03-07 - EVE L5_Medspa_IaC platform layer prototype

## Task

Design and prototype a declarative EVE L5_Medspa_IaC platform layer on top of the monorepo so a Medspa spec can compile into ontology, schema, voice, workflow, simulator, governance, and IaC artifacts.

## What shipped

- New platform package under `platform/l5_medspa_iac/`
- Thermo triage + routing logic (`tier_1`, `tier_2`, `full_matrix_routing`)
- Optimization sandbox with optional `networkx` / `PuLP` / `scipy` support and deterministic fallback
- Generator CLI: `scripts/generate_l5_medspa_platform.py`
- Sample client spec + generated bundle flow
- Architecture / rollout / blindspot docs under `docs/l5_medspa_iac/`
- Contract tests for parsing, routing, artifact emission, and CLI output

## Why

The repo already had the ingredients for ontology, voice, workflows, governance, and digital-twin simulation, but not a single declarative compiler surface that could produce them together from a client brief.

## Verification

- `python3 -m pytest tests/contracts/test_l5_medspa_platform_contract.py`
- `python3 scripts/generate_l5_medspa_platform.py --spec-file platform/l5_medspa_iac/specs/radiant_glow_medspa.json --output-dir /opt/cursor/artifacts/l5_platform_bundle --sandbox-only`
- `python3 -m pip install --user --break-system-packages -q -r platform/l5_medspa_iac/requirements.txt`
- `python3 scripts/generate_l5_medspa_platform.py --spec-file platform/l5_medspa_iac/specs/radiant_glow_medspa.json --output-dir /opt/cursor/artifacts/l5_platform_bundle_with_solver --sandbox-only`

## Notes

- The repo-level directory name `platform/` conflicts with the Python stdlib module name `platform`; the CLI and tests explicitly prepend `/workspace/platform` to `sys.path` and import `l5_medspa_iac` directly to avoid that collision.
- The solver stack is optional by design so the prototype still runs in minimal environments.
