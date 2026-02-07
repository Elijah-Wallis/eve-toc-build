# Task Note: MedSpa Launch Leak-Seal + MCP Hardening

Date: 2026-02-07

## Objective
- Seal launch-path leaks before outbound dialing.
- Ingest MedSpa CSV into campaign-scoped leads.
- Harden and validate n8n MCP integration for Retell orchestration.
- Add revenue API MCP coverage in repo.

## Implemented
- Added launch orchestration runtime:
  - `src/runtime/medspa_launch.py`
  - Registered task type `medspa.launch` in `src/runtime/registry_defaults.py`
  - Added Telegram commands in `src/runtime/telegram_router.py`:
    - `/launch-medspa <campaign_tag>`
    - `/launch-medspa-status <campaign_tag>`
- Added CSV importer:
  - `scripts/import_medspa_csv.py`
  - Strict category filter and phone normalization.
- Added n8n MCP ops scripts:
  - `scripts/sync_n8n_mcp_settings.py`
  - `scripts/validate_n8n_mcp.py`
  - `scripts/patch_workflows_for_campaign_filters.py`
  - `scripts/patch_workflow_env_bindings.py`
- Added revenue MCP servers:
  - `mcp_servers/retell_mcp/server.py`
  - `mcp_servers/twilio_mcp/server.py`
  - `mcp_servers/intelligence_mcp/server.py`
- Quarantined placeholder webhook surface:
  - `mcp_servers/api_handlers.py` now hard-fails with deprecation message.
- Updated runtime docs/config:
  - `.env.example`
  - `SKILLS.md`
  - `ecosystem.config.js`
- Updated workflow specs:
  - `workflows_n8n/openclaw_retell_call_dispatch.json`
  - `workflows_n8n/openclaw_nurture_engine.json`

## Live Verification
- CSV import report:
  - rows: 46
  - accepted: 37
  - excluded_non_medspa: 9
  - inserted_rows: 37
- MCP validation:
  - tools present: `search_workflows`, `get_workflow_details`, `execute_workflow`
  - workflows visible: dispatch, nurture, postcall, apify
- Dispatch workflow errors fixed:
  - source filter + lead limit expressions applied
  - daily-cap timestamp expression corrected
  - blocked `$env` expression in Set node removed for phone-number fields
- Launch task execution:
  - `medspa.launch` executes and blocks safely when canary has `call_sessions=0`
  - Current block reason observed: outside call window / no canary calls created at run time.

## Residual Risks
- Provider credential rotation is still operator action in 1Password/provider consoles.
- Retell web UI MCP form update requires authenticated session interaction.

## Additional Findings (Immutable n8n Executions)
- Execution traces `1354`-`1359` showed `Error in workflow` on Retell function endpoints when Config nodes used `$env.*`.
- Root cause from error context: `N8N_BLOCK_ENV_ACCESS_IN_NODE` policy denies env-variable reads in node expressions.
- Added runtime prevention in `src/runtime/medspa_launch.py`:
  - preflight now probes guardrail endpoints with invalid payloads and blocks launch on any workflow-level error.
  - this stops unsafe launch attempts immediately instead of failing later in canary.
