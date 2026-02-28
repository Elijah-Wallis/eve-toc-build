#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"
PYTHON_BIN="${OPENCLAW_ACCEPTANCE_PYTHON:-python3}"

if ! "$PYTHON_BIN" -c "import pytest" >/dev/null 2>&1; then
  VENV_DIR="${OPENCLAW_ACCEPTANCE_VENV:-/tmp/eve-acceptance-venv}"
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    python3 -m venv "$VENV_DIR"
    "${VENV_DIR}/bin/pip" install -q pytest pydantic requests
  fi
  PYTHON_BIN="${VENV_DIR}/bin/python"
fi

"$PYTHON_BIN" -m pytest tests/contracts -q "$@"
