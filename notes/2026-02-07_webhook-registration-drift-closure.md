# Task Note: Webhook Registration Drift Closure (Dispatch/Nurture)

Date: 2026-02-07

## Objective
- Eliminate `openclaw-retell-dispatch` / `openclaw-nurture-run` production webhook `404 not registered` failures.
- Close launch-path RED gate and verify stable behavior under repeated probes and queued task load.

## Root Cause
- Dispatch/nurture workflows were marked `active=true` in n8n API but production webhook registry was stale.
- Webhook nodes for these two workflows lacked `webhookId`, while registered guardrail tool workflows had stable `webhookId`.
- Remote workflow update scripts performed `PUT` without mandatory re-registration verification, allowing silent drift.

## Implemented
- Added shared runtime webhook client with self-heal:
  - `src/runtime/n8n_webhooks.py`
  - Candidate URL logic + one-time auto-heal for `404 not registered`.
  - Auto-heal resolves workflow by webhook path, patches missing `webhookId` if needed, then deactivates/reactivates and retries.
  - In-process cooldown guard limits recovery attempts to once per path per 60s.
- Refactored runtime call sites to use shared client:
  - `src/runtime/registry_defaults.py`
  - `src/runtime/medspa_launch.py`
- Added launch webhook preflight gate:
  - `launch_webhook_probe` in `MedspaLaunch.preflight()`
  - blocker key `launch_webhook_registry` when dispatch/nurture probe fails.
- Added lifecycle helper for scripts:
  - `scripts/n8n_workflow_lifecycle.py`
  - `get_workflow_by_name`, `force_reregister_workflow_webhooks`, `list_webhook_paths`, `verify_webhook_paths_registered`.
- Hardened update/deploy scripts:
  - `scripts/patch_workflows_for_campaign_filters.py` now sets stable webhook ids, force re-registers, verifies registration, and exits non-zero on failure.
  - `scripts/patch_workflow_env_bindings.py` now injects missing webhook ids, force re-registers updated webhook workflows, verifies registration, and exits non-zero on verification failure.
  - `scripts/deploy_retell_b2c_workflows.py` and `scripts/deploy_retell_personalization_workflows.py` now force re-register + verify webhook paths after remote updates.

## Verification
- `scripts/patch_workflows_for_campaign_filters.py --apply-remote`:
  - first run reproduced failure (`404 not registered`) before webhook-id patch.
  - post-fix run passed registration verification for both paths at `/webhook/*` with HTTP 200.
- `MedspaLaunch().preflight()`:
  - `overall_spatial.color = GREEN`
  - `launch_webhook_probe.status = ok`
  - dispatch+nurture probe status codes `200`.
- Live launch execution:
  - `/launch-medspa tx-medspa-2026-02-07` completed task execution (result status blocked by canary business gate), with dispatch trigger HTTP 200 and no webhook 404 errors.
- Stress tests:
  - 30 direct no-op probes each for dispatch and nurture: `60/60` success, `0` not-registered hits, `0` transport failures.
  - 20 queued `n8n.trigger` tasks (10 dispatch + 10 nurture no-op): `20/20` completed, `0` failed runs, `0` webhook-404 failures.
- `/status` after stress:
  - overall `GREEN`
  - last task `completed`.

## Operator Command Contract (Launch v2)
- `/launch-medspa <campaign_tag> [--mode manual|auto] [--profile conservative|balanced|aggressive] [--canary-size N] [--max-calls N] [--observation-seconds N]`
  - default mode is `manual`; default profile is `balanced`.
  - `manual` mode runs canary only and returns `awaiting_manual_approval` with `next_command`.
  - `auto` mode runs canary then full dispatch+nurture on pass.
- `/launch-medspa-approve <campaign_tag> [--profile conservative|balanced|aggressive] [--max-calls N] [--min-recent-canary-calls N] [--canary-lookback-hours N]`
  - requires preflight GREEN and minimum recent canary signal before full-ramp dispatch+nurture.

Profile defaults:
- `conservative`: canary `3`, max calls `20`, observation `90s`
- `balanced`: canary `5`, max calls `50`, observation `60s`
- `aggressive`: canary `8`, max calls `120`, observation `45s`
