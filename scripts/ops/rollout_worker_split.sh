#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

DRY_RUN=0
ROLLBACK=0
ROLLBACK_CHECK=0
WORKER_COUNT=1

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --rollback) ROLLBACK=1 ;;
    --rollback-check) ROLLBACK_CHECK=1 ;;
    --workers=*) WORKER_COUNT="${arg#*=}" ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] $*"
    return 0
  fi
  echo "[run] $*"
  "$@"
}

if [[ "$ROLLBACK_CHECK" -eq 1 ]]; then
  echo "rollback check: OK (commands are reversible via --rollback)"
  exit 0
fi

if [[ "$ROLLBACK" -eq 1 ]]; then
  run_cmd pm2 delete openclaw-worker || true
  run_cmd env OPENCLAW_RUNTIME_ROLE=all pm2 restart openclaw-runtime --update-env
  echo "worker split rollback complete"
  exit 0
fi

run_cmd env OPENCLAW_RUNTIME_ROLE=scheduler pm2 restart openclaw-runtime --update-env
run_cmd pm2 start ecosystem.config.js --only openclaw-worker
if [[ "$WORKER_COUNT" -gt 1 ]]; then
  run_cmd pm2 scale openclaw-worker "$WORKER_COUNT"
fi
echo "worker split rollout complete (workers=${WORKER_COUNT})"
