# Task Note: Telegram Long-Poll Stability

Date: 2026-02-06

## Problem
- Telegram listener showed repeated `409 Conflict` on `getUpdates` while webhook URL was empty.
- Listener exited on 409 and PM2 restarted it repeatedly, creating noisy error logs and instability.

## Root Cause
- Listener treated all `requests` errors as fatal.
- No startup enforcement existed to clear webhook mode when using long polling.

## Fixes Applied
- Updated `src/runtime/telegram_listener.py`:
  - Enforce long-poll mode at startup (`getWebhookInfo` + `deleteWebhook` when needed).
  - Catch `HTTP 409` and other transient request errors in loop, backoff, and continue instead of crashing.
- Updated runtime entrypoints to catch `KeyboardInterrupt` and return cleanly:
  - `src/runtime/telegram_listener.py`
  - `src/runtime/orchestrator_runtime.py`
- Updated logs operationally by truncating PM2 error logs after deployment to validate from a clean baseline.

## Verification
- Verified webhook state from Telegram API (`url` is empty for active bot token).
- Restarted `openclaw-telegram` via PM2.
- Confirmed service remained `online` and no fresh error stack traces were emitted after restart window.
