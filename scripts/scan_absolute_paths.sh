#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
PATTERN='(/Users/|/home/|C:\\Users\\)'
SELF_REL='scripts/scan_absolute_paths.sh'
EXCLUDE_FILES=(
  "scripts/ci/lint_no_absolute_paths.py"
  "scripts/scan_absolute_paths.sh"
)
SCAN_GLOBS=(
  "*.py"
  "*.go"
  "*.proto"
  "*.json"
  "*.yaml"
  "*.yml"
  "*.toml"
  "*.sh"
  "*.ini"
  "*.cfg"
  "*.env"
)
SCAN_DIRS=(
  "src"
  "services"
  "scripts"
  "policies/app"
  "platform"
  "docker"
)

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

FILES=()
for dir in "${SCAN_DIRS[@]}"; do
  if [[ -d "${dir}" ]]; then
    while IFS= read -r path; do
      FILES+=("${path}")
    done < <(git ls-files "${dir}")
  fi
done

FILTERED=()
for path in "${FILES[@]}"; do
  skip_file=0
  for excluded in "${EXCLUDE_FILES[@]}"; do
    if [[ "${path}" == "${excluded}" ]]; then
      skip_file=1
      break
    fi
  done
  if [[ "${skip_file}" -eq 1 ]]; then
    continue
  fi
  for glob in "${SCAN_GLOBS[@]}"; do
    if [[ "${path}" == ${glob} ]]; then
      FILTERED+=("${path}")
      break
    fi
  done
done

set +e
MATCHES="$(printf '%s\n' "${FILTERED[@]}" | rg -n --no-heading -e '.+' | cut -d: -f2- | xargs rg -n --no-heading --hidden --no-ignore-vcs -e "${PATTERN}" -- 2>/dev/null | rg -v "^${SELF_REL}:" || true)"
set -e

if [[ -n "${MATCHES}" ]]; then
  printf '%s\n' "${MATCHES}"
  exit 2
fi

printf '{"ok":true,"scan":"tracked_files","pattern":"%s"}\n' "${PATTERN}"
