#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${OPENCLAW_STATE_DIR:-$HOME/.openclaw-eve}"
MD="${STATE_DIR}/reports/daily/LATEST_REPORT.md"
PL="${STATE_DIR}/proposals/LATEST"

if [[ ! -f "$MD" ]]; then
  echo "missing report markdown: $MD" >&2
  echo "run the proactive loop once: python3 -m src.runtime.proactive_review.daily_review --mode offline --profile fast --once" >&2
  exit 2
fi
if [[ ! -e "$PL" ]]; then
  echo "missing latest proposals path: $PL" >&2
  echo "run the proactive loop once: python3 -m src.runtime.proactive_review.daily_review --mode offline --profile fast --once" >&2
  exit 2
fi

open "$MD"
open "$PL"

echo "opened morning report + proposals"
