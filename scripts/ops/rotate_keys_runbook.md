# Key Rotation Runbook (EVE/OpenClaw)

## Scope
Rotate all high-risk tokens observed in runtime/config/process surfaces:
- `OPENCLAW_GATEWAY_TOKEN`
- `OPENCLAW_TELEGRAM_BOT_TOKEN`
- `SUPABASE_SERVICE_ROLE_KEY`
- `N8N_API_KEY`
- `N8N_MCP_TOKEN` / `N8N_MCP_ACCESS_TOKEN`
- `RETELL_AI_KEY`
- `TWILIO_AUTH_TOKEN`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`

## Preconditions
1. `launchd` gateway and `pm2` runtime are healthy.
2. Secret files are provisioned under `${OPENCLAW_STATE_DIR}/credentials` (state dir defaults to `${HOME}/.openclaw-eve`).
3. `OPENCLAW_SECRETS_SOURCE=file` and `OPENCLAW_ALLOW_ENV_SECRET_FALLBACK=0`.

## Procedure
1. Create new credentials in each upstream provider.
2. Write new values to secret files with restrictive permissions (`chmod 600`).
3. Remove old values from `.openclaw_env`, shell profiles, and ad-hoc scripts.
4. Restart processes:
   - `launchctl kickstart -k gui/$(id -u)/ai.openclaw.eve`
   - `pm2 restart openclaw-runtime openclaw-telegram --update-env`
5. Run post-rotation checks:
   - `python3 scripts/ops/secret_exposure_scan.py`
   - `python3 scripts/acceptance/run_acceptance.py --ids AT-001,AT-002,AT-011`

## Rollback
1. Temporarily set `OPENCLAW_SECRETS_SOURCE=env` and `OPENCLAW_ALLOW_ENV_SECRET_FALLBACK=1`.
2. Restart processes.
3. Restore previous secret material only long enough to recover service, then repeat rotation.
