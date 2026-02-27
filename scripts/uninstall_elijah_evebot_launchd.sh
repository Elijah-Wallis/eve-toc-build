#!/usr/bin/env bash
set -euo pipefail

USER_UID="$(id -u)"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
DAILY_LABEL="com.openclaw.elijah_evebot_daily"
WEEKLY_LABEL="com.openclaw.elijah_evebot_weekly_deep"
HEARTBEAT_LABEL="com.openclaw.elijah_evebot_heartbeat_hourly"
DAILY_PLIST="${LAUNCH_AGENTS_DIR}/${DAILY_LABEL}.plist"
WEEKLY_PLIST="${LAUNCH_AGENTS_DIR}/${WEEKLY_LABEL}.plist"
HEARTBEAT_PLIST="${LAUNCH_AGENTS_DIR}/${HEARTBEAT_LABEL}.plist"

remove_one() {
  local plist="$1"
  local label="$2"
  if [[ -f "${plist}" ]]; then
    launchctl bootout "gui/${USER_UID}" "${plist}" 2>/dev/null || true
    rm -f "${plist}"
  else
    launchctl bootout "gui/${USER_UID}/${label}" 2>/dev/null || true
  fi
}

remove_one "${DAILY_PLIST}" "${DAILY_LABEL}"
remove_one "${WEEKLY_PLIST}" "${WEEKLY_LABEL}"
remove_one "${HEARTBEAT_PLIST}" "${HEARTBEAT_LABEL}"

shopt -s nullglob
legacy_candidates=(
  "${LAUNCH_AGENTS_DIR}"/ai.openclaw.elijah-evebot-daily*.plist
  "${LAUNCH_AGENTS_DIR}"/ai.openclaw.elijah-evebot-weekly-deep*.plist
  "${LAUNCH_AGENTS_DIR}"/ai.openclaw.elijah-evebot-*.plist
  "${LAUNCH_AGENTS_DIR}"/ai.openclaw.elijah_evebot_daily*.plist
  "${LAUNCH_AGENTS_DIR}"/ai.openclaw.elijah_evebot_weekly_deep*.plist
  "${LAUNCH_AGENTS_DIR}"/ai.openclaw.elijah_evebot_*.plist
)
shopt -u nullglob

for plist in "${legacy_candidates[@]}"; do
  [[ -f "${plist}" ]] || continue
  launchctl bootout "gui/${USER_UID}" "${plist}" 2>/dev/null || true
  rm -f "${plist}"
done

loaded_labels="$(launchctl list 2>/dev/null | awk '{print $3}' | rg '^ai\.openclaw\.elijah[-_]evebot' || true)"
while IFS= read -r label; do
  [[ -n "${label}" ]] || continue
  if compgen -G "${LAUNCH_AGENTS_DIR}/${label}*.plist" >/dev/null; then
    continue
  fi
  launchctl bootout "gui/${USER_UID}/${label}" 2>/dev/null || true
done <<< "${loaded_labels}"

echo "uninstalled Elijah_EveBot launchd jobs"
exit 0
