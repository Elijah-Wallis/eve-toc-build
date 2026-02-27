#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

CAMPAIGN_TAG="${1:-}"
LOOKBACK_HOURS="${LOOKBACK_HOURS:-24}"
LIVE_FLAG="${LIVE_FLAG:---live}"

echo "[1/4] Emit immutable telemetry probe"
python3 scripts/ops/emit_telemetry_probe.py

echo "[2/4] Verify immutable telemetry hash chain"
python3 scripts/ops/verify_immutable_telemetry.py --require-signed --allow-legacy-interleaving

echo "[3/4] Reconcile post-call ingestion"
if [[ -n "$CAMPAIGN_TAG" ]]; then
  python3 scripts/ops/reconcile_postcall_now.py --campaign-tag "$CAMPAIGN_TAG" --lookback-hours "$LOOKBACK_HOURS"
else
  python3 scripts/ops/reconcile_postcall_now.py --lookback-hours "$LOOKBACK_HOURS"
fi

echo "[4/4] Run live gates (AT-006 + AT-011)"
python3 scripts/acceptance/run_acceptance.py --ids AT-006,AT-011 "$LIVE_FLAG"

echo "Data integrity protocol: PASS"
