#!/usr/bin/env bash
set -euo pipefail

# Single-command launcher: avoids direnv/cd confusion by invoking via absolute paths.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

HOST="${EVE_DASHBOARD_HOST:-127.0.0.1}"
PORT="${EVE_DASHBOARD_PORT:-7331}"
PORT_MAX="${EVE_DASHBOARD_PORT_MAX:-7340}"

# Least action: if a dashboard is already running, just open it instead of spawning another server.
OPEN_HOST="${HOST}"
if [[ "${OPEN_HOST}" == "0.0.0.0" || "${OPEN_HOST}" == "::" ]]; then
  OPEN_HOST="127.0.0.1"
fi
if command -v curl >/dev/null 2>&1; then
  for p in $(seq "${PORT}" "${PORT_MAX}"); do
    if curl -fsS --max-time 0.25 "http://${OPEN_HOST}:${p}/api/ping" >/dev/null 2>&1; then
      python3 - <<PY >/dev/null 2>&1 || true
import webbrowser
webbrowser.open("http://${OPEN_HOST}:${p}", new=1, autoraise=True)
PY
      echo "Eve dashboard already running: http://${OPEN_HOST}:${p}"
      exit 0
    fi
  done
fi

exec python3 "${ROOT_DIR}/scripts/dashboard/health_server.py" \
  --host "${HOST}" \
  --port "${PORT}" \
  --port-max "${PORT_MAX}" \
  --open \
  --quiet
