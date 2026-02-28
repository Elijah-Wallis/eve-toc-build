#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../../.." && pwd)}"
GOLANG_IMAGE="${GOLANG_IMAGE:-golang:latest}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 2
fi
if ! docker info >/dev/null 2>&1; then
  echo "docker daemon is unavailable" >&2
  exit 2
fi

docker run --rm \
  -v "${REPO_ROOT}:/workspace" \
  -w /workspace/services/retell-brain-go \
  "${GOLANG_IMAGE}" \
  go vet ./...
