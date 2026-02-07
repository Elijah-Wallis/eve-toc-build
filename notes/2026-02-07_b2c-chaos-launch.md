# Task Note: B2C Chaos-Hardened Demo + Appointment Automation

Date: 2026-02-07

## Objective
- Configure B2C Retell agent for adversarial/chaotic patient conversations.
- Add low-friction free demo options (callback + web session token).
- Add booking + reminder automation aimed at maximizing show rate.

## Implemented
- Added B2C prompt + KB:
  - `Business_Code/retell_system_prompt_medspa_b2c_v1.md`
  - `Business_Code/retell_kb_medspa_b2c.md`
- Added B2C workflow deployer:
  - `scripts/deploy_retell_b2c_workflows.py`
  - Workflows:
    - `openclaw_retell_fn_b2c_context`
    - `openclaw_retell_fn_b2c_quote`
    - `openclaw_retell_fn_b2c_availability`
    - `openclaw_retell_fn_b2c_book_appointment`
    - `openclaw_retell_fn_b2c_demo_call`
    - `openclaw_retell_fn_b2c_web_demo`
    - `openclaw_b2c_showrate_nudge`
- Added B2C Retell configurator:
  - `scripts/configure_retell_b2c_agent.py`
- Expanded Retell MCP server with web-call support:
  - `mcp_servers/retell_mcp/server.py` adds `retell.create_web_call`

## Current Gate Risk
- n8n instance currently returns workflow runtime error when Config nodes use `$env.*` due workspace policy (`N8N_BLOCK_ENV_ACCESS_IN_NODE`).
- This is platform-level and blocks guardrail endpoints until env access is enabled in n8n workspace settings.

## Go Requirement Tie-In
- Launch remains correctly blocked by preflight guardrail probe until this policy is resolved.
