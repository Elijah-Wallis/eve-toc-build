#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
OPENCLAW_STATE_DIR="${OPENCLAW_STATE_DIR:-${HOME}/.openclaw-eve}"
PYTHON_BIN="$(command -v python3)"
USER_UID="$(id -u)"
WITH_WEEKLY_DEEP=0
WITH_HEARTBEAT_HOURLY=0

for arg in "$@"; do
  case "$arg" in
    --with-weekly-deep)
      WITH_WEEKLY_DEEP=1
      ;;
    --with-heartbeat-hourly)
      WITH_HEARTBEAT_HOURLY=1
      ;;
    *)
      echo "unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3 is required" >&2
  exit 2
fi

DAILY_LABEL="com.openclaw.elijah_evebot_daily"
WEEKLY_LABEL="com.openclaw.elijah_evebot_weekly_deep"
HEARTBEAT_LABEL="com.openclaw.elijah_evebot_heartbeat_hourly"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
DAILY_PLIST="${LAUNCH_AGENTS_DIR}/${DAILY_LABEL}.plist"
WEEKLY_PLIST="${LAUNCH_AGENTS_DIR}/${WEEKLY_LABEL}.plist"
HEARTBEAT_PLIST="${LAUNCH_AGENTS_DIR}/${HEARTBEAT_LABEL}.plist"

mkdir -p "${LAUNCH_AGENTS_DIR}" "${OPENCLAW_STATE_DIR}/logs"

cleanup_legacy_installs() {
  shopt -s nullglob
  local legacy_candidates=(
    "${LAUNCH_AGENTS_DIR}"/ai.openclaw.elijah-evebot-daily*.plist
    "${LAUNCH_AGENTS_DIR}"/ai.openclaw.elijah-evebot-weekly-deep*.plist
    "${LAUNCH_AGENTS_DIR}"/ai.openclaw.elijah-evebot-*.plist
    "${LAUNCH_AGENTS_DIR}"/ai.openclaw.elijah_evebot_daily*.plist
    "${LAUNCH_AGENTS_DIR}"/ai.openclaw.elijah_evebot_weekly_deep*.plist
    "${LAUNCH_AGENTS_DIR}"/ai.openclaw.elijah_evebot_*.plist
  )
  shopt -u nullglob

  local legacy_plist
  for legacy_plist in "${legacy_candidates[@]}"; do
    [[ -f "${legacy_plist}" ]] || continue
    launchctl bootout "gui/${USER_UID}" "${legacy_plist}" 2>/dev/null || true
    rm -f "${legacy_plist}"
  done

  local loaded_labels
  loaded_labels="$(launchctl list 2>/dev/null | awk '{print $3}' | rg '^ai\.openclaw\.elijah[-_]evebot' || true)"
  local label
  while IFS= read -r label; do
    [[ -n "${label}" ]] || continue
    if compgen -G "${LAUNCH_AGENTS_DIR}/${label}*.plist" >/dev/null; then
      continue
    fi
    launchctl bootout "gui/${USER_UID}/${label}" 2>/dev/null || true
  done <<< "${loaded_labels}"
}

install_one() {
  local template="$1"
  local plist="$2"
  local label="$3"

  sed \
    -e "s#__LABEL__#${label}#g" \
    -e "s#__PYTHON_BIN__#${PYTHON_BIN}#g" \
    -e "s#__REPO_ROOT__#${REPO_ROOT}#g" \
    -e "s#__OPENCLAW_STATE_DIR__#${OPENCLAW_STATE_DIR}#g" \
    "${template}" > "${plist}"

  plutil -lint "${plist}" >/dev/null
  launchctl bootout "gui/${USER_UID}" "${plist}" 2>/dev/null || true
  launchctl bootstrap "gui/${USER_UID}" "${plist}"
  launchctl enable "gui/${USER_UID}/${label}" 2>/dev/null || true
  launchctl kickstart -k "gui/${USER_UID}/${label}" 2>/dev/null || true
}

cleanup_legacy_installs

install_one "${REPO_ROOT}/ops/launchd/elijah_evebot_daily.plist" "${DAILY_PLIST}" "${DAILY_LABEL}"

if [[ "${WITH_WEEKLY_DEEP}" == "1" ]]; then
  install_one "${REPO_ROOT}/ops/launchd/elijah_evebot_weekly_deep.plist" "${WEEKLY_PLIST}" "${WEEKLY_LABEL}"
fi

if [[ "${WITH_HEARTBEAT_HOURLY}" == "1" ]]; then
  install_one "${REPO_ROOT}/ops/launchd/elijah_evebot_heartbeat_hourly.plist" "${HEARTBEAT_PLIST}" "${HEARTBEAT_LABEL}"
fi

echo "installed ${DAILY_LABEL}"
if [[ "${WITH_WEEKLY_DEEP}" == "1" ]]; then
  echo "installed ${WEEKLY_LABEL}"
fi
if [[ "${WITH_HEARTBEAT_HOURLY}" == "1" ]]; then
  echo "installed ${HEARTBEAT_LABEL}"
fi
