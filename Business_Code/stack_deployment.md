# Stack Deployment Policy (Single-Owner Ops)

## Ownership model
- `launchd` owns OpenClaw gateway (`ai.openclaw.eve` on port `19001`).
- `pm2` owns runtime workers and custom Telegram listener (`openclaw-runtime`, `openclaw-telegram`, optional `openclaw-worker`).
- Gateway Telegram plugin must stay disabled when custom listener is active.

## Why
- Prevents split-brain supervision (`launchd` vs `pm2`) and gateway restart storms.
- Prevents Telegram `getUpdates` 409 conflicts from multiple pollers.
- Keeps worker scale-out independent from gateway lifecycle.

## Standard status checks
1. `launchctl list | rg ai.openclaw`
2. `pm2 list`
3. `python3 scripts/ops/check_telegram_conflicts.py --window-minutes 30`
4. `python3 scripts/ops/runtime_slo_check.py --window-minutes 60`
5. `python3 scripts/ops/secret_exposure_scan.py`
6. `python3 scripts/ops/v6_canary_scorecard.py --hours 24 --source-regex '^tx-medspa-' --min-human-answered 40`

## Standard restart flow
1. Gateway:
   - `launchctl kickstart -k gui/$(id -u)/ai.openclaw.eve`
2. Runtime + listener:
   - `pm2 restart openclaw-runtime openclaw-telegram --update-env`
3. Optional workers:
   - `pm2 start ecosystem.config.js --only openclaw-worker`
4. Secret argv scrub (no key rotation):
   - `bash scripts/ops/scrub_secret_argv_processes.sh`

## Worker split rollout
- Default: `OPENCLAW_RUNTIME_ROLE=all` on `openclaw-runtime`.
- Scale-out mode:
  - Set `openclaw-runtime` to `scheduler`.
  - Start one or more `openclaw-worker` processes with `OPENCLAW_RUNTIME_ROLE=worker`.
  - Validate duplicate prevention before increasing worker count.

## Retell Prompt Rollout
- Promote V6 prompt on B2B agent:
  - `python3 scripts/configure_retell_b2b_agent.py --agent-id \"$RETELL_AGENT_B2B_ID\" --prompt-version v6`
- Roll back to V5 prompt:
  - `python3 scripts/configure_retell_b2b_agent.py --agent-id \"$RETELL_AGENT_B2B_ID\" --prompt-version v5`
- Configure B2B with websocket + bidirectional:
  - `python3 scripts/configure_retell_b2b_agent.py --agent-id \"$RETELL_AGENT_B2B_ID\" --prompt-version v6 --websocket-url \"$RETELL_LLM_WEBSOCKET_URL\" --bidirectional-mode on`
- Configure B2C with expanded tool stack + websocket:
  - `python3 scripts/configure_retell_b2c_agent.py --agent-id \"$RETELL_AGENT_B2C_ID\" --websocket-url \"$RETELL_LLM_WEBSOCKET_URL\" --bidirectional-mode on`

## Rollback
- Runtime split rollback:
  - `pm2 delete openclaw-worker`
  - set `OPENCLAW_RUNTIME_ROLE=all` for `openclaw-runtime`, then restart.
- Supervisor rollback:
  - use `scripts/ops/converge_gateway_and_ingress_owner.sh --rollback`.

## Docker note
- Docker remains optional for local n8n experimentation only.
- Production runtime authority for this host is `launchd + pm2`, not Docker.

## CPOM Operational Guardrails (MedSpa B2B)
- Scope is administrative workflow and revenue-ops support, not clinical care.
- Prompts, tools, and workflows must not generate diagnosis/treatment/prescribing content.
- Any clinical question must be deferred to licensed providers/medical leadership.
- Public legal pages, runtime prompt artifacts, and KB content must maintain the same non-clinical boundary language.
