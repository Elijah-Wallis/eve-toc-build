# 2026-03-07 - Cloud Python scientific stack bootstrap

## Task

Ensure the optional scientific stack used by `platform/l5_medspa_iac` is available in cloud-like environments for:

- `scripts/generate_l5_medspa_platform.py`
- platform contract tests
- acceptance harness paths that exercise those imports

## What changed

- Added `scripts/setup_cloud_python_scientific_stack.sh`
- Hardened `scripts/acceptance/run_contract_suite.sh` to:
  - tolerate missing `venv` support
  - fall back to user-site installs with `--break-system-packages`
  - ensure `yaml`, `networkx`, `pulp`, and `scipy` are present before contract tests
  - honor explicit pytest target arguments instead of always forcing the full contracts directory
- Updated `docker/openclaw/Dockerfile` to preinstall:
  - `python3-pip`
  - `python3-venv`
  - platform scientific requirements from `platform/l5_medspa_iac/requirements.txt`

## Verification

- `bash scripts/setup_cloud_python_scientific_stack.sh`
- `python3 - <<'PY' ... import yaml, networkx, pulp, scipy ...`
- `bash scripts/acceptance/run_contract_suite.sh tests/contracts/test_l5_medspa_platform_contract.py`

## Notes

- There is no repo-local Cursor cloud environment manifest in this workspace, so the fix is implemented through bootstrap scripts plus the Docker environment definition that exists in-repo.
