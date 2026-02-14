#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

PATTERN='(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z-]{10,}|ghp_[0-9A-Za-z]{36,}|AIza[0-9A-Za-z_-]{35}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}|SUPABASE_SERVICE_ROLE_KEY[[:space:]]*=[[:space:]]*[A-Za-z0-9._-]{20,})'

matches=$(git ls-files | rg -n -H --no-messages -e "$PATTERN" || true)

if [[ -n "$matches" ]]; then
  echo "$matches"
  echo "FAIL: potential secrets found in tracked files" >&2
  exit 2
fi

echo "OK: no strict secret patterns found"
