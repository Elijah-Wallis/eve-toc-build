#!/usr/bin/env bash
set -euo pipefail

RUN_VALIDATE_ONLY=0
if [[ "${1:-}" == "--run" ]]; then
  RUN_VALIDATE_ONLY=1
  shift
fi

if [[ $# -ne 1 ]]; then
  echo "usage: $0 [--run] <proposal_dir>" >&2
  exit 2
fi

PROPOSAL_DIR="$1"
META="$PROPOSAL_DIR/meta.json"

if [[ ! -f "$META" ]]; then
  echo "missing meta file: $META" >&2
  exit 2
fi

git rev-parse --show-toplevel >/dev/null
cd "$(git rev-parse --show-toplevel)"

PROPOSAL_KIND="$(python3 -c 'import json,sys; print((json.load(open(sys.argv[1])) or {}).get(\"proposal_kind\",\"code_patch\"))' "$META")"
BASE_SHA="$(python3 -c 'import json,sys; print((json.load(open(sys.argv[1])) or {}).get(\"base_sha\",\"\"))' "$META")"
CUR_SHA="$(git rev-parse HEAD)"

echo "current HEAD: $CUR_SHA"
echo "proposal kind: $PROPOSAL_KIND"
if [[ -n "$BASE_SHA" ]]; then
  echo "proposal base_sha: $BASE_SHA"
  if [[ "$CUR_SHA" != "$BASE_SHA" ]]; then
    echo "warning: current HEAD differs from proposal base_sha" >&2
  fi
fi

if [[ "$PROPOSAL_KIND" == "validate_only" ]]; then
  echo "validate_only proposal: no patch to apply"
  echo "execution_commands:"
  python3 - "$META" <<'PY' | while IFS= read -r cmd; do
import json, sys
meta_path = sys.argv[1]
meta = json.load(open(meta_path))
cmds = meta.get("execution_commands") or []
for cmd in cmds:
    print(str(cmd))
PY
    printf "%q\n" "$cmd"
  done

  if [[ "$RUN_VALIDATE_ONLY" != "1" ]]; then
    echo "note: re-run with --run to execute these commands"
    exit 0
  fi

  mapfile -t COMMANDS < <(python3 - "$META" <<'PY'
import json, sys
meta = json.load(open(sys.argv[1]))
cmds = meta.get("execution_commands") or []
for cmd in cmds:
    print(str(cmd))
PY
  )
  if [[ "${#COMMANDS[@]}" -eq 0 ]]; then
    echo "no execution_commands found in meta: $META" >&2
    exit 2
  fi
  for cmd in "${COMMANDS[@]}"; do
    echo "+ $cmd"
    bash -lc "$cmd"
  done
  exit 0
fi

PATCH="$PROPOSAL_DIR/change.patch"
if [[ ! -f "$PATCH" ]]; then
  echo "missing patch file: $PATCH" >&2
  exit 2
fi

if ! git apply --check "$PATCH"; then
  echo "Try: git apply --3way $PATCH" >&2
  exit 2
fi

git apply "$PATCH"
echo "applied: $PATCH"
