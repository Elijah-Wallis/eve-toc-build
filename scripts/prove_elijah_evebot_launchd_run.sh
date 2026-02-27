#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
STATE_DIR="${OPENCLAW_STATE_DIR:-$HOME/.openclaw-eve}"
DAILY_LABEL="com.openclaw.elijah_evebot_daily"
HB="${STATE_DIR}/heartbeat/elijah_evebot_heartbeat.json"
RPT="${STATE_DIR}/reports/daily/LATEST_REPORT.json"

if [[ ! -f "$HB" ]]; then
  echo "missing heartbeat: $HB" >&2
  echo "guidance: run the bot once manually:" >&2
  echo "python3 -m src.runtime.proactive_review.daily_review --mode offline --profile fast --once" >&2
  exit 2
fi
if [[ ! -f "$RPT" ]]; then
  echo "missing latest report json: $RPT" >&2
  echo "guidance: run the bot once manually:" >&2
  echo "python3 -m src.runtime.proactive_review.daily_review --mode offline --profile fast --once" >&2
  exit 2
fi

if ! launchctl print "gui/${UID}/${DAILY_LABEL}" >/dev/null 2>&1; then
  echo "launchd label not loaded: ${DAILY_LABEL}" >&2
  echo "reinstall with: bash ${REPO_ROOT}/scripts/install_elijah_evebot_launchd.sh" >&2
  exit 2
fi

read_hb() {
  python3 - "$HB" <<'PY'
import json, sys
p = sys.argv[1]
obj = json.load(open(p))
print((obj.get("run_id") or "") + "\t" + (obj.get("finished_at") or ""))
PY
}

read_mtime() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys
print(int(Path(sys.argv[1]).stat().st_mtime))
PY
}

IFS=$'\t' read -r PRE_RUN_ID PRE_FINISHED <<<"$(read_hb)"
PRE_RPT_MTIME="$(read_mtime "$RPT")"

echo "pre run_id: $PRE_RUN_ID"
echo "pre finished_at: $PRE_FINISHED"
echo "pre report_mtime: $PRE_RPT_MTIME"

launchctl kickstart -k "gui/${UID}/${DAILY_LABEL}"

PASS=0
NEW_RUN_ID="$PRE_RUN_ID"
NEW_FINISHED="$PRE_FINISHED"
NEW_RPT_MTIME="$PRE_RPT_MTIME"

for _ in $(seq 1 30); do
  sleep 2
  IFS=$'\t' read -r NEW_RUN_ID NEW_FINISHED <<<"$(read_hb)"
  NEW_RPT_MTIME="$(read_mtime "$RPT")"

  RUN_OR_FINISHED_ADVANCED=0
  if [[ "$NEW_RUN_ID" != "$PRE_RUN_ID" ]]; then
    RUN_OR_FINISHED_ADVANCED=1
  elif [[ "$NEW_FINISHED" != "$PRE_FINISHED" ]]; then
    RUN_OR_FINISHED_ADVANCED=1
  fi

  if [[ "$RUN_OR_FINISHED_ADVANCED" == "1" && "$NEW_RPT_MTIME" -gt "$PRE_RPT_MTIME" ]]; then
    PASS=1
    break
  fi
done

if [[ "$PASS" == "1" ]]; then
  echo "PASS: launchd run advanced heartbeat/report artifacts"
  echo "new run_id: $NEW_RUN_ID"
  echo "new finished_at: $NEW_FINISHED"
  echo "new report_mtime: $NEW_RPT_MTIME"
  exit 0
fi

echo "FAIL: no qualifying artifact advance detected within timeout" >&2
echo "old run_id: $PRE_RUN_ID" >&2
echo "new run_id: $NEW_RUN_ID" >&2
echo "old finished_at: $PRE_FINISHED" >&2
echo "new finished_at: $NEW_FINISHED" >&2
echo "old report_mtime: $PRE_RPT_MTIME" >&2
echo "new report_mtime: $NEW_RPT_MTIME" >&2
echo "remediation:" >&2
echo "  bash ${REPO_ROOT}/scripts/install_elijah_evebot_launchd.sh" >&2
echo "  bash ${REPO_ROOT}/scripts/verify_elijah_evebot_launchd.sh" >&2
echo "  launchctl print \"gui/${UID}/${DAILY_LABEL}\"" >&2
exit 3
