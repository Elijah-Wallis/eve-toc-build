#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

collect_candidates() {
  ps ax -o pid= -o command= | awk '
    /supergateway/ && /--streamableHttp/ && /--header/ && /authorization:Bearer/ && $2 !~ /awk|rg|grep/ {
      pid=$1
      $1=""
      sub(/^[[:space:]]+/, "", $0)
      print pid "|" $0
    }
  '
}

redact_command() {
  local raw="$1"
  printf '%s\n' "$raw" | sed -E 's/(authorization:Bearer[[:space:]]+)[^[:space:]]+/\1[REDACTED]/Ig'
}

kill_pid() {
  local pid="$1"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] kill -TERM $pid"
    return 0
  fi
  kill -TERM "$pid" 2>/dev/null || true
}

hard_kill_pid() {
  local pid="$1"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] kill -KILL $pid"
    return 0
  fi
  kill -KILL "$pid" 2>/dev/null || true
}

mapfile -t matches < <(collect_candidates)

if [[ "${#matches[@]}" -eq 0 ]]; then
  echo "no secret-bearing argv processes found"
  exit 0
fi

echo "found ${#matches[@]} secret-bearing argv process(es):"
for row in "${matches[@]}"; do
  pid="${row%%|*}"
  cmd="${row#*|}"
  echo "  pid=${pid} cmd=$(redact_command "$cmd")"
done

for row in "${matches[@]}"; do
  pid="${row%%|*}"
  kill_pid "$pid"
done

if [[ "$DRY_RUN" -eq 0 ]]; then
  sleep 1
fi

for row in "${matches[@]}"; do
  pid="${row%%|*}"
  if ps -p "$pid" >/dev/null 2>&1; then
    hard_kill_pid "$pid"
  fi
done

echo "secret argv scrub complete"
