#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
PATTERN='(/Users/|/home/|C:\\Users\\)'
SELF_REL='scripts/scan_absolute_paths.sh'

if ! command -v git >/dev/null 2>&1; then
  echo "git is required" >&2
  exit 2
fi
if ! command -v rg >/dev/null 2>&1; then
  echo "rg is required" >&2
  exit 2
fi

cd "${REPO_ROOT}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "must run inside a git repository" >&2
  exit 2
fi

# Scan tracked files only for deterministic CI/local behavior.
set +e
MATCHES="$(git ls-files -z | xargs -0 rg -n --no-heading --hidden --no-ignore-vcs -e "${PATTERN}" -- 2>/dev/null | rg -v "^${SELF_REL}:" || true)"
set -e

if [[ -n "${MATCHES}" ]]; then
  printf '%s\n' "${MATCHES}"
  exit 2
fi

printf '{"ok":true,"scan":"tracked_files","pattern":"%s"}\n' "${PATTERN}"
