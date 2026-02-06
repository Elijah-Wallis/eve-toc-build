# CODEX Kernel Rules

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

## Notes Index
- `notes/2026-02-06_telegram-longpoll-stability.md`
