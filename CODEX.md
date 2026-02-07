# CODEX Kernel Rules

## Scope Split Contract
- Global identity + reasoning protocol belongs in System Instructions and applies across all repos.
- `CODEX.md` stores repo-local, testable operating rules only.
- `/notes` stores incident/task records with fix + verification evidence.

## Persistent Self Correction
- After every logic correction or bug fix, add a permanent rule to this file.
- For every project/task, create a note in `/notes` and record what was fixed, why it failed, and how verification was done.
- Link the active note from kernel context (`MEMORY.md`) so runtime context can reload the latest constraints.

## Runtime Reliability Rules
- Telegram listener must run in long-poll mode only. On startup, call `getWebhookInfo`; if webhook URL is set, call `deleteWebhook`.
- Telegram `getUpdates` `409 Conflict` must never crash the listener loop; treat as recoverable and retry with backoff.
- Runtime entrypoints must catch `KeyboardInterrupt` and exit `0` so PM2 restarts do not pollute error logs with expected shutdown traces.
- n8n workflow dispatch must try compatible webhook URL shapes before failing (`/{workflow}`, `/webhook/{workflow}`, `/webhook-test/{workflow}`).
- Supabase cron registration must be idempotent (`on_conflict=name` with conflict-safe fallback update).
- Campaign launch automation must hard-scope lead selection by `source_filter` and enforce canary caps before full ramp.
- n8n Set-node environment expressions can be blocked by workspace policy (`N8N_BLOCK_ENV_ACCESS_IN_NODE`); validate workflow executions after config edits and avoid `$env` expressions in blocked nodes.
- Launch preflight must include guardrail webhook probes (`openclaw-retell-fn-log-insight`, `openclaw-retell-fn-set-followup`, `openclaw-retell-fn-enrich-intel`) and hard-block if any probe returns `Error in workflow` or unexpected response.
- B2C appointment automation must always store booked appointment + reminder idempotency events before triggering reminder calls, so show-rate nudges are deduped and auditable.
- If n8n Cloud blocks `$env` and Variables are unavailable on the current license, patch remote workflows with literal Config bindings via `scripts/patch_workflow_env_bindings.py --apply-remote --remote-only --mode literal` and keep secret placeholders out of repo files.

## Secret-Handling Rules
- Never commit raw credentials/tokens in code, workflow JSON, docs, or tests.
- Workflow config values for secrets must use env expressions (example: `={{$env.SUPABASE_SERVICE_ROLE_KEY}}`).
- If push protection fails, sanitize files and rewrite local unpublished history before retrying push.

## Verification Gates
- For runtime changes: verify PM2 process status, `/status`, and relevant command paths.
- For Telegram listener changes: verify webhook URL is empty and no new `409` errors after stabilization.
- For logging fixes: rotate/truncate target logs, restart services, then re-check log files for new critical traces.
- For MCP compiler changes: execute full pipeline (`scripts/run_traffic_to_mcp_pipeline.py`) and require zero non-zero codes for npm install/build/client checks across generated tools.

## Traffic Compiler Rules
- Source of truth is observed traffic in `~/.openclaw-eve/runtime/api_traffic.jsonl`; do not fabricate endpoints.
- Runtime must auto-capture outbound HTTP via `src/runtime/http_traffic.py` when `OPENCLAW_CAPTURE_TRAFFIC != 0`.
- Generated MCP packages must include exactly: `package.json`, `tsconfig.json`, `src/index.ts`, `client.py`, `.env.example`, `README.md`.
- Regeneration must clear stale generated tool directories before emitting new packages.
- Python harness execution must use an isolated venv under `generated/mcp_from_traffic/.venv` to avoid PEP 668 system package constraints.

## Notes Index
- `notes/2026-02-06_telegram-longpoll-stability.md`
- `notes/2026-02-06_scope-split-governance.md`
- `notes/2026-02-06_traffic-to-mcp-compiler.md`
- `notes/2026-02-07_medspa-launch-leak-seal.md`
