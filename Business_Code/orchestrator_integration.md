# Orchestrator Integration

## Auto-enqueue packs
- Lead Ops (hourly): `openclaw-apify-ingest`, `openclaw-retell-dispatch`, `openclaw-nurture-run`
- Sales Intel (daily): `reports.daily`

## Scheduled task loop
Run the runtime loop:

```bash
python3 -m src.runtime.orchestrator_runtime
```

## Telegram graph trigger
Command format:
- `/runpack openclaw-apify-ingest`
- `/graph {"nodes": [...], "context": {...}}`
- `/tasks`
- `/status`

## Command queue bridge
The runtime loop watches the `commandQueueFile` from `openclaw.json`.
Any line written there is treated as a Telegram-style command.

## Telegram listener
The `openclaw-telegram` PM2 app runs a long-polling listener using your bot token.
Set `OPENCLAW_TELEGRAM_USER_ID` to your Telegram user ID for gating.

## Revenue ops cron
`/runpack` now creates/updates a cron job in `cron_jobs` and runs once immediately.
