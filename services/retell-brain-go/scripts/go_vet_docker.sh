#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../../.." && pwd)}"
GOLANG_IMAGE="${GOLANG_IMAGE:-golang:latest}"
GO_RESOLVER="${SCRIPT_DIR}/resolve_go_toolchain.sh"

if ! command -v docker >/dev/null 2>&1; then
  GO_BIN="$("${GO_RESOLVER}")"
  cd "${REPO_ROOT}/services/retell-brain-go"
  "${GO_BIN}" vet ./...
  exit 0
fi
if ! docker info >/dev/null 2>&1; then
  GO_BIN="$("${GO_RESOLVER}")"
  cd "${REPO_ROOT}/services/retell-brain-go"
  "${GO_BIN}" vet ./...
  exit 0
fi

docker run --rm \
  -v "${REPO_ROOT}:/workspace" \
  -w /workspace/services/retell-brain-go \
  "${GOLANG_IMAGE}" \
  go vet ./...
