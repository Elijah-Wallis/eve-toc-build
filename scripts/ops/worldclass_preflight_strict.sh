#!/usr/bin/env bash
set -euo pipefail

# Fail-closed wrapper around worldclass_preflight.sh:
# - If FAIL>0 => fail
# - If WARN>0 => fail (strict mode)

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel)}"

tmp="$(mktemp)"
set +e
(cd "${REPO_ROOT}" && bash scripts/ops/worldclass_preflight.sh) 2>&1 | tee "${tmp}"
code="${PIPESTATUS[0]}"
set -e

if [[ "${code}" -ne 0 ]]; then
  rm -f "${tmp}"
  exit "${code}"
fi

summary="$(grep -E 'FAIL=[0-9]+[[:space:]]+WARN=[0-9]+' "${tmp}" | tail -n 1 || true)"
rm -f "${tmp}"

if [[ "${summary}" =~ FAIL=([0-9]+)[[:space:]]+WARN=([0-9]+) ]]; then
  fail="${BASH_REMATCH[1]}"
  warn="${BASH_REMATCH[2]}"
else
  fail=1
  warn=1
fi

if [[ "${fail}" -eq 0 && "${warn}" -eq 0 ]]; then
  exit 0
fi

echo "FAIL (strict): FAIL=${fail} WARN=${warn}" >&2
exit 2

