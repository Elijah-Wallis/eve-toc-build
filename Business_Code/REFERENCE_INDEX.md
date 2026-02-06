# OpenClaw Reference Index

This is the single master file that lists all key system files.

## Runtime Control Plane
- `src/runtime/`
  - `model_router.py`
  - `task_engine.py`
  - `task_registry.py`
  - `context_store.py`
  - `skill_graph.py`
  - `skill_executor.py`
  - `graph_runner.py`
  - `cron_scheduler.py`
  - `telegram_router.py`
  - `telegram_listener.py`
  - `orchestrator_runtime.py`
  - `telemetry.py`
  - `env_loader.py`

## CLI
- `openclaw_cli.py`
- `scripts/compile_mcp_from_traffic.py`
- `scripts/run_traffic_to_mcp_pipeline.py`

## Protocol Omega
- `src/omega/`

## MCP
- `mcp_servers/`

## n8n Workflows
- `workflows_n8n/`

## Supabase
- `supabase/schema.sql`
- `supabase/upgrade_runtime.sql`

## Orchestration
- `ecosystem.config.js`
- `Business_Code/orchestrator_integration.md`

## Deployment
- `Business_Code/stack_deployment.md`
- `docker/compose.yaml`

## Architecture & Specs
- `ARCHITECTURE.md`
- `Business_Code/upgrade_baseline.md`
- `Business_Code/skill_metadata.md`
- `Business_Code/business_packs.md`

## Execution Playbooks
- `Business_Code/weekly_kpi_dashboard.md`
- `Business_Code/operating_cadence.md`

## IP Protection
- `Business_Code/SOP_IP.md`
- `Business_Code/SOP_TRAFFIC_TO_MCP_COMPILER.md`

## Generated MCP Artifacts
- `generated/mcp_from_traffic/manifest.json`
- `SKILLS.md` (Auto-Generated MCP Skills section)
