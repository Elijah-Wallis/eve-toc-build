#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${OPENCLAW_STATE_DIR:-$HOME/.openclaw-eve}"
DAILY_LABEL="com.openclaw.elijah_evebot_daily"
WEEKLY_LABEL="com.openclaw.elijah_evebot_weekly_deep"
HEARTBEAT_LABEL="com.openclaw.elijah_evebot_heartbeat_hourly"
DAILY_PLIST="$HOME/Library/LaunchAgents/${DAILY_LABEL}.plist"
WEEKLY_PLIST="$HOME/Library/LaunchAgents/${WEEKLY_LABEL}.plist"
HEARTBEAT_PLIST="$HOME/Library/LaunchAgents/${HEARTBEAT_LABEL}.plist"

echo "== LaunchAgents files =="
ls -la "$HOME/Library/LaunchAgents" | grep -i evebot || true

echo "== launchctl list (filtered) =="
launchctl list | grep -i evebot || true

echo "== DAILY job details =="
launchctl print "gui/${UID}/${DAILY_LABEL}" || true
plutil -p "$DAILY_PLIST" || true

echo "== WEEKLY job details (if installed) =="
if [ -f "$WEEKLY_PLIST" ]; then
  launchctl print "gui/${UID}/${WEEKLY_LABEL}" || true
  plutil -p "$WEEKLY_PLIST" || true
fi

echo "== HOURLY heartbeat job details (if installed) =="
if [ -f "$HEARTBEAT_PLIST" ]; then
  launchctl print "gui/${UID}/com.openclaw.elijah_evebot_heartbeat_hourly" || true
  plutil -p "$HOME/Library/LaunchAgents/com.openclaw.elijah_evebot_heartbeat_hourly.plist" || true
fi

echo "== Logs (tail) =="
tail -n 80 "${STATE_DIR}/logs/elijah_evebot_daily.log" 2>/dev/null || true
tail -n 80 "${STATE_DIR}/logs/elijah_evebot_weekly_deep.log" 2>/dev/null || true
tail -n 80 "${STATE_DIR}/logs/elijah_evebot_heartbeat_hourly.log" 2>/dev/null || true

echo "== Done =="
