#!/usr/bin/env bash
set -euo pipefail

# Guardrail: policy files in the workspace template must remain symlinks to the
# canonical workspace state, so edits propagate deterministically across the ontology.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

require_symlink() {
  local path="$1"
  local expected_suffix="$2"

  if [[ ! -e "$path" && ! -L "$path" ]]; then
    echo "ERROR: missing required path: $path" >&2
    return 1
  fi

  if [[ ! -L "$path" ]]; then
    echo "ERROR: expected symlink but found regular file: $path" >&2
    return 1
  fi

  local target
  target="$(readlink "$path")"
  if [[ "$target" != *"$expected_suffix" ]]; then
    echo "ERROR: unexpected symlink target for $path" >&2
    echo "  got:      $target" >&2
    echo "  expected: *$expected_suffix" >&2
    return 1
  fi
}

require_symlink "$ROOT_DIR/openclaw_workspace_template/SOUL.md" "/workspace/SOUL.md"
require_symlink "$ROOT_DIR/openclaw_workspace_template/HEARTBEAT.md" "/workspace/HEARTBEAT.md"

echo "OK: policy symlink invariants hold."

