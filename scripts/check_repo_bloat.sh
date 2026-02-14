#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

cd "${REPO_ROOT}"

if [[ "${CI:-0}" != "1" ]]; then
  echo '{"ok":true,"check":"repo_bloat","mode":"non_ci_skip"}'
  exit 0
fi

if [[ -d "generated" ]]; then
  size_mb="$(du -sm generated | awk '{print $1}')"
  if [[ "${size_mb}" -gt 100 ]]; then
    echo "generated/ is ${size_mb}MB in CI context; use \${OPENCLAW_STATE_DIR}/generated via resolve_generated_dir()" >&2
    exit 2
  fi
fi

echo '{"ok":true,"check":"repo_bloat"}'
