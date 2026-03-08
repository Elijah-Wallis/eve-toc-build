#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-platform/l5_medspa_iac/requirements.txt}"

read -r -d '' CHECK_SCRIPT <<'PY' || true
import importlib.util
import sys

required = ["yaml", "networkx", "pulp", "scipy"]
missing = [name for name in required if importlib.util.find_spec(name) is None]
if missing:
    print(",".join(missing))
    sys.exit(1)
PY

if "$PYTHON_BIN" -c "$CHECK_SCRIPT" >/dev/null 2>&1; then
  echo "Optional scientific stack already available for ${PYTHON_BIN}."
  exit 0
fi

echo "Installing optional scientific stack for ${PYTHON_BIN}..."
"$PYTHON_BIN" -m pip install --user --break-system-packages -q -r "$REQUIREMENTS_FILE"
echo "Optional scientific stack installed."
