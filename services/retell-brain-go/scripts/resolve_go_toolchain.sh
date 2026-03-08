#!/usr/bin/env bash
set -euo pipefail

REQUIRED_VERSION="${OPENCLAW_GO_REQUIRED_VERSION:-1.23.6}"
GO_CACHE_DIR="${OPENCLAW_GO_TOOLCHAIN_DIR:-/tmp/openclaw-go-toolchain}"

version_ge() {
  [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | tail -n1)" = "$1" ]
}

current_go_bin() {
  if [[ -n "${OPENCLAW_GO_BIN:-}" && -x "${OPENCLAW_GO_BIN}" ]]; then
    printf '%s\n' "${OPENCLAW_GO_BIN}"
    return
  fi
  if command -v go >/dev/null 2>&1; then
    command -v go
  fi
}

go_version_value() {
  local go_bin="$1"
  "$go_bin" version | awk '{print $3}' | sed 's/^go//'
}

download_go_toolchain() {
  local target_dir="${GO_CACHE_DIR}/${REQUIRED_VERSION}"
  local archive="${target_dir}.tar.gz"
  if [[ ! -x "${target_dir}/go/bin/go" ]]; then
    mkdir -p "${GO_CACHE_DIR}"
    curl -fsSLo "${archive}" "https://go.dev/dl/go${REQUIRED_VERSION}.linux-amd64.tar.gz"
    rm -rf "${target_dir}"
    mkdir -p "${target_dir}"
    tar -xzf "${archive}" -C "${target_dir}"
  fi
  printf '%s\n' "${target_dir}/go/bin/go"
}

GO_BIN="$(current_go_bin || true)"
if [[ -n "${GO_BIN}" ]]; then
  GO_VERSION="$(go_version_value "${GO_BIN}")"
  if version_ge "${GO_VERSION}" "${REQUIRED_VERSION}"; then
    printf '%s\n' "${GO_BIN}"
    exit 0
  fi
fi

download_go_toolchain
