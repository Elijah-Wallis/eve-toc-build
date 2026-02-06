# Task Note: Traffic-to-MCP Compiler

Date: 2026-02-06

## Objective
- Capture real outbound OpenClaw traffic and compile each unique API pattern into standalone MCP tool packages.
- Attach generated tools into repo skill index and verify with build + live MCP client harness.

## Implementation
- Added HTTP traffic recorder:
  - `src/runtime/http_traffic.py`
  - Hooked from `src/runtime/env_loader.py` when `OPENCLAW_CAPTURE_TRAFFIC` is enabled.
- Added compiler:
  - `scripts/compile_mcp_from_traffic.py`
  - Inputs: `~/.openclaw-eve/runtime/api_traffic.jsonl`
  - Outputs: `generated/mcp_from_traffic/<tool_name>/...`
  - Auto-updates `SKILLS.md` with generated MCP tool entries.
- Added full pipeline runner:
  - `scripts/run_traffic_to_mcp_pipeline.py`
  - Steps: generate traffic -> compile -> npm install/build per tool -> python harness execution.
  - Uses venv at `generated/mcp_from_traffic/.venv` for `mcp` dependency isolation.

## Verification
- Executed full pipeline end-to-end.
- Pipeline report: `generated/mcp_from_traffic/pipeline_report.json` (ignored from git).
- Final status: all generated tools returned `npm_install=0`, `npm_build=0`, `client=0`.

## Generated Tool Families
- n8n API/webhook endpoints (`get_workflows`, `create_webhook`, `create_resource`)
- Supabase REST endpoints (`get_tasks`, `create_tasks`, `update_tasks`, `get_task_runs`, `create_task_runs`, etc.)
