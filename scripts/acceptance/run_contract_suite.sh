#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"
PYTHON_BIN="${OPENCLAW_ACCEPTANCE_PYTHON:-python3}"
SCIENTIFIC_STACK_SCRIPT="$ROOT_DIR/scripts/setup_cloud_python_scientific_stack.sh"

require_modules() {
  local py_bin="$1"
  shift
  "$py_bin" - "$@" <<'PY'
import importlib.util
import sys

modules = sys.argv[1:]
missing = [name for name in modules if importlib.util.find_spec(name) is None]
if missing:
    print(",".join(missing))
    sys.exit(1)
PY
}

if ! "$PYTHON_BIN" -c "import pytest" >/dev/null 2>&1; then
  VENV_DIR="${OPENCLAW_ACCEPTANCE_VENV:-/tmp/eve-acceptance-venv}"
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    if python3 -m venv "$VENV_DIR" >/dev/null 2>&1; then
      "${VENV_DIR}/bin/pip" install -q pytest pydantic requests
    else
      python3 -m pip install --user --break-system-packages -q pytest pydantic requests
      PYTHON_BIN="python3"
    fi
  fi
  if [[ -x "${VENV_DIR}/bin/python" ]]; then
    PYTHON_BIN="${VENV_DIR}/bin/python"
  fi
fi

if ! require_modules "$PYTHON_BIN" yaml networkx pulp scipy >/dev/null 2>&1; then
  bash "$SCIENTIFIC_STACK_SCRIPT"
fi

if [[ "$#" -gt 0 ]]; then
  "$PYTHON_BIN" -m pytest -q "$@"
else
  "$PYTHON_BIN" -m pytest tests/contracts -q
fi
