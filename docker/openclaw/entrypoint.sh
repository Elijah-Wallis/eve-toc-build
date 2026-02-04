#!/usr/bin/env bash
set -euo pipefail

profile="${OPENCLAW_PROFILE:-eve}"
gateway_port="${OPENCLAW_GATEWAY_PORT:-19001}"
gateway_bind="${OPENCLAW_GATEWAY_BIND:-lan}"
gateway_token="${OPENCLAW_GATEWAY_TOKEN:-}"

if [[ -z "$gateway_token" ]]; then
  echo "ERROR: missing OPENCLAW_GATEWAY_TOKEN" >&2
  exit 2
fi

workspace_root="/root/.openclaw-${profile}/workspace"
mkdir -p "$workspace_root"
if [[ ! -f "${workspace_root}/BOOTSTRAP.md" ]]; then
  cp -R /template/. "$workspace_root/"
fi

auth_choice="skip"
auth_flags=()
if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
  auth_choice="openrouter-api-key"
  auth_flags+=(--openrouter-api-key "${OPENROUTER_API_KEY}")
elif [[ -n "${OPENAI_API_KEY:-}" ]]; then
  auth_choice="openai-api-key"
  auth_flags+=(--openai-api-key "${OPENAI_API_KEY}")
elif [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  auth_choice="anthropic-api-key"
  auth_flags+=(--anthropic-api-key "${ANTHROPIC_API_KEY}")
fi

openclaw --profile "$profile" onboard \
  --non-interactive \
  --accept-risk \
  --flow manual \
  --mode local \
  --auth-choice "$auth_choice" \
  --gateway-port "$gateway_port" \
  --gateway-bind "$gateway_bind" \
  --gateway-auth token \
  --gateway-token "$gateway_token" \
  --skip-ui \
  --skip-health \
  --no-install-daemon \
  --workspace "$workspace_root" \
  "${auth_flags[@]}" >/dev/null

if [[ -n "${OPENCLAW_TELEGRAM_BOT_TOKEN:-}" ]]; then
  openclaw --profile "$profile" channels add \
    --channel telegram \
    --account default \
    --name "Eve (OpenClaw)" \
    --token "${OPENCLAW_TELEGRAM_BOT_TOKEN}" >/dev/null || true
fi

openclaw --profile "$profile" doctor --non-interactive --fix >/dev/null 2>&1 || true

if [[ -n "${OPENCLAW_DEFAULT_MODEL:-}" ]]; then
  openclaw --profile "$profile" models set "${OPENCLAW_DEFAULT_MODEL}" >/dev/null 2>&1 || true
fi

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf "%s" "$s"
}

if [[ -n "${OPENCLAW_FALLBACK_MODELS:-}" ]]; then
  openclaw --profile "$profile" models fallbacks clear >/dev/null 2>&1 || true
  IFS=',' read -r -a fallbacks <<<"${OPENCLAW_FALLBACK_MODELS}"
  for model in "${fallbacks[@]}"; do
    model_trimmed="$(trim "$model")"
    [[ -z "$model_trimmed" ]] && continue
    openclaw --profile "$profile" models fallbacks add "$model_trimmed" >/dev/null 2>&1 || true
  done
fi

if [[ -n "${OPENCLAW_MODEL_ALIASES:-}" ]]; then
  IFS=',' read -r -a aliases <<<"${OPENCLAW_MODEL_ALIASES}"
  for pair in "${aliases[@]}"; do
    pair_trimmed="$(trim "$pair")"
    [[ -z "$pair_trimmed" ]] && continue
    alias_name="${pair_trimmed%%:*}"
    alias_model="${pair_trimmed#*:}"
    if [[ -n "$alias_name" && -n "$alias_model" && "$alias_name" != "$alias_model" ]]; then
      openclaw --profile "$profile" models aliases add "$alias_name" "$alias_model" >/dev/null 2>&1 || true
    fi
  done
fi

openclaw --profile "$profile" gateway run \
  --allow-unconfigured \
  --port "$gateway_port" \
  --bind "$gateway_bind" \
  --token "$gateway_token" \
  --compact &
gateway_pid="$!"

tries=0
until openclaw --profile "$profile" gateway health --timeout 10000 >/dev/null 2>&1; do
  tries=$((tries + 1))
  if [[ "$tries" -gt 50 ]]; then
    echo "ERROR: gateway failed health check" >&2
    kill "$gateway_pid" 2>/dev/null || true
    exit 3
  fi
  sleep 0.2
done

openclaw --profile "$profile" system heartbeat enable >/dev/null 2>&1 || true

if [[ -n "${OPENCLAW_TELEGRAM_CHAT_ID:-}" ]]; then
  openclaw --profile "$profile" cron add \
    --name drumbeat \
    --description "Proactive constraint scan + safe next action + report" \
    --every 30m \
    --agent main \
    --thinking medium \
    --message "PROTOCOL ZERO. Identify the current constraint in /repo (use fast file search). Execute one safe, reversible improvement. Report: what changed, why, and next constraint." \
    --deliver \
    --channel telegram \
    --to "${OPENCLAW_TELEGRAM_CHAT_ID}" \
    --best-effort-deliver >/dev/null 2>&1 || true

  openclaw --profile "$profile" cron add \
    --name daily-brief \
    --description "Daily brief: actions, yield, next constraint" \
    --every 24h \
    --agent main \
    --thinking low \
    --message "Summarize the last 24h: actions taken, outcomes, failures, next constraint. Keep it short and signal-only." \
    --deliver \
    --channel telegram \
    --to "${OPENCLAW_TELEGRAM_CHAT_ID}" \
    --best-effort-deliver >/dev/null 2>&1 || true

  openclaw --profile "$profile" message send \
    --channel telegram \
    --target "${OPENCLAW_TELEGRAM_CHAT_ID}" \
    --message "EVE online. Gateway=ws://localhost:${gateway_port} (bind=${gateway_bind}). Cron: drumbeat(30m), daily-brief(24h). Repo mounted at /repo (ro)." >/dev/null 2>&1 || true
fi

wait "$gateway_pid"
