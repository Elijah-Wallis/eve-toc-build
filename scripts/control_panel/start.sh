#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
APP="${REPO_ROOT}/scripts/control_panel/app.py"
PORT="${EVE_CONTROL_PANEL_PORT:-8501}"

if ! command -v streamlit &>/dev/null; then
    echo "[eve-control-panel] Installing streamlit + python-dotenv..."
    pip install --quiet streamlit python-dotenv
elif ! python3 -c "import dotenv" 2>/dev/null; then
    echo "[eve-control-panel] Installing python-dotenv..."
    pip install --quiet python-dotenv
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  EVE Launch Control Center"
echo "  http://localhost:${PORT}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exec streamlit run "${APP}" \
    --server.port="${PORT}" \
    --server.headless=true \
    --server.address="0.0.0.0" \
    --browser.gatherUsageStats=false \
    --theme.base="dark" \
    --theme.primaryColor="#00f5ff" \
    --theme.backgroundColor="#050508" \
    --theme.secondaryBackgroundColor="#0a0a10" \
    --theme.textColor="#e0e8f0"
