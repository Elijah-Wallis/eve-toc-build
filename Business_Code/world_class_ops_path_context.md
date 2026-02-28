# World-Class Ops Path Context

## Canonical roots
- `REPO_ROOT`: repo root (`git rev-parse --show-toplevel`)
- `OPENCLAW_STATE_DIR`: runtime state root (default `${HOME}/.openclaw-eve`)
- `OPENCLAW_ENV_FILE`: `${OPENCLAW_STATE_DIR%/*}/.openclaw_env`
- `CLOUDFLARE_ENV_FILE`: `${OPENCLAW_STATE_DIR}/cloudflare.env`

## Why this exists
This file captures path and dependency truth so we do not lose context during incident response or chat compaction.

## Critical files and paths
- Transcript schema migration:
  - `${REPO_ROOT}/supabase/upgrade_transcripts.sql`
- Full schema bootstrap:
  - `${REPO_ROOT}/supabase/schema.sql`
- Transcript sync/backfill:
  - `${REPO_ROOT}/scripts/ops/sync_call_transcripts.py`
- Retell B2B config:
  - `${REPO_ROOT}/scripts/configure_retell_b2b_agent.py`
- Retell B2C config:
  - `${REPO_ROOT}/scripts/configure_retell_b2c_agent.py`
- Acceptance runner:
  - `${REPO_ROOT}/scripts/acceptance/run_acceptance.py`

## Required env keys
Loaded from `${OPENCLAW_ENV_FILE}` by `src/runtime/env_loader.py`.

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `RETELL_AI_KEY`
- `RETELL_AGENT_B2B_ID`
- `RETELL_AGENT_B2C_ID`
- Optional (needed for websocket mode):
  - `RETELL_LLM_WEBSOCKET_URL`

## Cloudflare requirements for websocket mode
- `CLOUDFLARE_API_TOKEN` must be non-empty in `${CLOUDFLARE_ENV_FILE}` if Cloudflare API automation is expected.
- Public websocket hostname must resolve in DNS.
- Hostname route must terminate to the local websocket service path expected by Retell.

## Fast operational checks
1. Run preflight:
   - `bash ${REPO_ROOT}/scripts/ops/worldclass_preflight.sh`
2. Confirm transcript table exists:
   - `python3 ${REPO_ROOT}/scripts/ops/sync_call_transcripts.py --lookback-hours 1 --print-table`
3. Configure Retell agents:
   - `python3 ${REPO_ROOT}/scripts/configure_retell_b2b_agent.py --agent-id "$RETELL_AGENT_B2B_ID" --prompt-version v6 --strict-agent-update`
   - `python3 ${REPO_ROOT}/scripts/configure_retell_b2c_agent.py --agent-id "$RETELL_AGENT_B2C_ID" --strict-agent-update`

## Failure mode map
- `call_transcripts table is missing`:
  - Apply `${REPO_ROOT}/supabase/upgrade_transcripts.sql` in Supabase SQL editor.
- Agent sounds degraded/choppy after websocket switch:
  - Verify websocket hostname DNS and handshake before keeping websocket mode enabled.
  - If not healthy, use non-websocket `retell-llm` mode for continuity.
- Agent has `tool_count = 0`:
  - Re-run configure scripts and verify `general_tools_count` is non-zero via `get-retell-llm`.

