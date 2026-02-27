#!/usr/bin/env bash
set -euo pipefail

UID_NUM="$(id -u)"
STATE_DIR="${OPENCLAW_STATE_DIR:-$HOME/.openclaw-eve}"
SNAPSHOT_FILE="${STATE_DIR}/runtime/gateway_ingress_snapshot.json"
PROFILE_CONFIG="${STATE_DIR}/openclaw.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRUB_SCRIPT="${SCRIPT_DIR}/scrub_secret_argv_processes.sh"

DRY_RUN=0
ROLLBACK=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --rollback) ROLLBACK=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] $*"
    return 0
  fi
  echo "[run] $*"
  "$@"
}

snapshot_state() {
  mkdir -p "$(dirname "$SNAPSHOT_FILE")"
  python3 - "$SNAPSHOT_FILE" "$PROFILE_CONFIG" <<'PY'
import json
import pathlib
import subprocess
import sys

snapshot_file = pathlib.Path(sys.argv[1])
profile = pathlib.Path(sys.argv[2])

def has_pm2(name: str) -> bool:
    try:
        raw = subprocess.check_output(["pm2", "jlist"], text=True)
    except Exception:
        return False
    try:
        rows = json.loads(raw)
    except Exception:
        return False
    return any(str(row.get("name")) == name for row in rows)

def launchd_loaded(label: str) -> bool:
    try:
        out = subprocess.check_output(["launchctl", "list"], text=True)
    except Exception:
        return False
    return any(label in line for line in out.splitlines())

plugin_enabled = False
if profile.exists():
    try:
        cfg = json.loads(profile.read_text())
        plugin_enabled = bool(((cfg.get("plugins") or {}).get("entries") or {}).get("telegram", {}).get("enabled", False))
    except Exception:
        plugin_enabled = False

snapshot = {
    "pm2_openclaw_present": has_pm2("openclaw"),
    "launchd_gateway_loaded": launchd_loaded("ai.openclaw.gateway"),
    "launchd_eve_loaded": launchd_loaded("ai.openclaw.eve"),
    "telegram_plugin_enabled": plugin_enabled,
}
snapshot_file.write_text(json.dumps(snapshot, indent=2))
print(json.dumps(snapshot))
PY
}

set_telegram_plugin() {
  local desired="$1"
  python3 - "$PROFILE_CONFIG" "$desired" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
desired = sys.argv[2].strip().lower() == "true"
if not path.exists():
    print("profile config missing; skipping")
    sys.exit(0)
cfg = json.loads(path.read_text())
plugins = cfg.setdefault("plugins", {})
entries = plugins.setdefault("entries", {})
telegram = entries.setdefault("telegram", {})
telegram["enabled"] = desired
path.write_text(json.dumps(cfg, indent=2) + "\n")
print(f"telegram plugin enabled={desired}")
PY
}

if [[ "$ROLLBACK" -eq 1 ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] restore from $SNAPSHOT_FILE"
    exit 0
  fi
  if [[ ! -f "$SNAPSHOT_FILE" ]]; then
    echo "snapshot not found: $SNAPSHOT_FILE" >&2
    exit 1
  fi
  python3 - "$SNAPSHOT_FILE" "$PROFILE_CONFIG" <<'PY'
import json
import pathlib
import subprocess
import sys

snapshot = json.loads(pathlib.Path(sys.argv[1]).read_text())
profile = pathlib.Path(sys.argv[2])

if snapshot.get("launchd_gateway_loaded"):
    subprocess.run(["launchctl", "kickstart", "-k", f"gui/{subprocess.check_output(['id','-u'], text=True).strip()}/ai.openclaw.gateway"], check=False)
if snapshot.get("pm2_openclaw_present"):
    subprocess.run(["pm2", "start", "ecosystem.config.js", "--only", "openclaw"], check=False)
if profile.exists():
    cfg = json.loads(profile.read_text())
    plugins = cfg.setdefault("plugins", {}).setdefault("entries", {}).setdefault("telegram", {})
    plugins["enabled"] = bool(snapshot.get("telegram_plugin_enabled"))
    profile.write_text(json.dumps(cfg, indent=2) + "\n")
print("rollback applied")
PY
  exit 0
fi

snapshot_state

run_cmd launchctl bootout "gui/${UID_NUM}/ai.openclaw.gateway" || true

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] disable telegram plugin in $PROFILE_CONFIG"
else
  set_telegram_plugin "false"
fi

run_cmd launchctl kickstart -k "gui/${UID_NUM}/ai.openclaw.eve" || true
run_cmd pm2 delete openclaw || true
if [[ -x "$SCRUB_SCRIPT" ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    run_cmd "$SCRUB_SCRIPT" --dry-run || true
  else
    run_cmd "$SCRUB_SCRIPT" || true
  fi
else
  echo "warning: scrub script missing or not executable: $SCRUB_SCRIPT" >&2
fi

echo "converged: launchd owns gateway, custom listener owns Telegram ingress"
