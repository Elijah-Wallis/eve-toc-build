#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel)}"
STATE_DIR="${OPENCLAW_STATE_DIR:-$HOME/.openclaw-eve}"
OPENCLAW_ENV_FILE="${STATE_DIR%/*}/.openclaw_env"
CLOUDFLARE_ENV_FILE="${STATE_DIR}/cloudflare.env"

FAIL=0
WARN=0

say_ok() { echo "OK   $*"; }
say_warn() { echo "WARN $*"; WARN=$((WARN + 1)); }
say_fail() { echo "FAIL $*"; FAIL=$((FAIL + 1)); }

echo "== World-Class Ops Preflight =="
echo "REPO_ROOT=${REPO_ROOT}"
echo "STATE_DIR=${STATE_DIR}"
echo "OPENCLAW_ENV_FILE=${OPENCLAW_ENV_FILE}"
echo "CLOUDFLARE_ENV_FILE=${CLOUDFLARE_ENV_FILE}"

[[ -d "${REPO_ROOT}" ]] && say_ok "repo root present" || say_fail "repo root missing"
[[ -f "${REPO_ROOT}/supabase/upgrade_transcripts.sql" ]] && say_ok "upgrade_transcripts.sql present" || say_fail "upgrade_transcripts.sql missing"
[[ -f "${REPO_ROOT}/scripts/ops/sync_call_transcripts.py" ]] && say_ok "sync_call_transcripts.py present" || say_fail "sync_call_transcripts.py missing"
[[ -f "${REPO_ROOT}/scripts/configure_retell_b2b_agent.py" ]] && say_ok "configure_retell_b2b_agent.py present" || say_fail "configure_retell_b2b_agent.py missing"
[[ -f "${REPO_ROOT}/scripts/configure_retell_b2c_agent.py" ]] && say_ok "configure_retell_b2c_agent.py present" || say_fail "configure_retell_b2c_agent.py missing"

if [[ -f "${OPENCLAW_ENV_FILE}" ]]; then
  say_ok ".openclaw_env present"
else
  say_fail ".openclaw_env missing at ${OPENCLAW_ENV_FILE}"
fi

if [[ -f "${CLOUDFLARE_ENV_FILE}" ]]; then
  token_value="$(awk -F= '/^CLOUDFLARE_API_TOKEN=/{print $2}' "${CLOUDFLARE_ENV_FILE}" | tr -d '"' | tr -d "'")"
  if [[ -n "${token_value}" ]]; then
    say_ok "CLOUDFLARE_API_TOKEN populated"
  else
    say_warn "CLOUDFLARE_API_TOKEN is empty (Cloudflare API automation disabled)"
  fi
else
  say_warn "cloudflare.env missing (Cloudflare API automation disabled)"
fi

python3 - <<'PY' || FAIL=$((FAIL + 1))
from src.runtime.env_loader import load_env_file
import os
import sys

load_env_file()
required = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "RETELL_AI_KEY",
    "RETELL_AGENT_B2B_ID",
    "RETELL_AGENT_B2C_ID",
]
missing = [k for k in required if not os.environ.get(k)]
if missing:
    print("FAIL missing required env keys:", ",".join(missing))
    sys.exit(1)
print("OK   required env keys present")

ws_url = os.environ.get("RETELL_LLM_WEBSOCKET_URL", "").strip()
if not ws_url:
    print("WARN RETELL_LLM_WEBSOCKET_URL missing (websocket mode not configured)")
else:
    print("OK   RETELL_LLM_WEBSOCKET_URL present")
PY

python3 - <<'PY' || WARN=$((WARN + 1))
from src.runtime.env_loader import load_env_file
import os
import socket
from urllib.parse import urlparse

load_env_file()
ws_url = os.environ.get("RETELL_LLM_WEBSOCKET_URL", "").strip()
if not ws_url:
    print("WARN websocket DNS check skipped (no RETELL_LLM_WEBSOCKET_URL)")
    raise SystemExit(0)
host = urlparse(ws_url).hostname
if not host:
    print("WARN websocket DNS check skipped (invalid URL)")
    raise SystemExit(0)
try:
    print("OK   websocket host resolves:", host, socket.gethostbyname(host))
except Exception as exc:  # noqa: BLE001
    print("WARN websocket host does not resolve:", host, str(exc))
    raise SystemExit(1)
PY

python3 - <<'PY' || WARN=$((WARN + 1))
from src.runtime.env_loader import load_env_file
import os
import requests

load_env_file()
url = os.environ.get("SUPABASE_URL", "").rstrip("/")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
if not url or not key:
    print("WARN Supabase schema check skipped (missing env)")
    raise SystemExit(1)
headers = {"apikey": key, "Authorization": f"Bearer {key}"}
resp = requests.get(
    f"{url}/rest/v1/call_transcripts",
    headers=headers,
    params={"select": "id,recording_url", "limit": "1"},
    timeout=15,
)
if resp.status_code == 200:
    print("OK   call_transcripts table available with recording_url select")
else:
    print("WARN call_transcripts unavailable:", resp.status_code, (resp.text or "")[:180])
    raise SystemExit(1)
PY

if curl -fsS -m 5 "http://127.0.0.1:19001/" >/dev/null 2>&1; then
  say_ok "local gateway reachable at 127.0.0.1:19001"
else
  say_warn "local gateway not reachable at 127.0.0.1:19001"
fi

echo "== Summary =="
echo "FAIL=${FAIL} WARN=${WARN}"
if [[ "${FAIL}" -gt 0 ]]; then
  exit 2
fi
exit 0

