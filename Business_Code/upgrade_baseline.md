# Upgrade Baseline (OpenClaw Elijah_EveBot)

## Runtime entrypoints
- `eve_dashboard.py` (PM2 auto-start)
- `orchestrator.py` (skill loader wrapper)
- `omega_factory.py`, `omega_audit.py`, `trigger_n8n_workflow.py`
- `.agents/skills/*` (skill implementations)

## Skill loaders
- Root wrappers load `.agents/skills/*.py` using importlib.
- Skills are currently stand-alone Python modules.

## MCP servers
- `mcp_servers/apify_mcp/server.py`
- `mcp_servers/supabase_mcp/server.py`
- n8n MCP via supergateway configured externally.

## n8n workflows
- `workflows_n8n/openclaw_apify_scrape_ingest.json`
- `workflows_n8n/openclaw_retell_call_dispatch.json`
- `workflows_n8n/openclaw_retell_postcall_ingest.json`
- `workflows_n8n/openclaw_daily_metrics.json`
- `workflows_n8n/openclaw_nurture_engine.json`

## Supabase schema
- `supabase/schema.sql` (lead-gen tables)
- No task/memory tables in baseline.

## Model provider settings
- `openclaw.json` references Anthropic model `claude-3-5-sonnet-20240620`.
- Model routing not centralized; errors like "unknown model" are possible.

## Findings
- No durable task queue present.
- No long-context memory store present.
- No skill graph orchestration layer present.
- No CLI control plane for ops.
