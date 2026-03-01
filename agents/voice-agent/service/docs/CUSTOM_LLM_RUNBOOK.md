# Custom LLM (BYOM) Runbook

## One-command enable (after tunnel is running)

From repo root, with `RETELL_LLM_WEBSOCKET_URL` and `RETELL_AI_KEY` set:

```bash
python3 scripts/configure_retell_b2b_agent.py --agent-id agent_5d6f2744acfc79e26ddce13af2 --prompt-version v13.3 --custom-llm
```

This switches the agent to BYOM (custom-llm-websocket), keeps the full V13.3 prompt on the Retell LLM (for fallback), and sets bidirectional + interrupt handling. The voice-agent must already be running and reachable at `RETELL_LLM_WEBSOCKET_URL` (e.g. `wss://voice-agent.yourdomain.com/llm-websocket`; Retell appends `/{call_id}`).

## Enable custom LLM with full V13.3 prompt (full steps)

1. **Start the voice-agent and expose it** (e.g. Cloudflare Tunnel):
   ```bash
   cd agents/voice-agent/service
   # Optional: set B2B_V133_PROMPT_PATH to repo path to mcp_servers/b2b_workflow.yaml
   export B2B_V133_PROMPT_PATH="/path/to/eve-toc-build/mcp_servers/b2b_workflow.yaml"
   export CONVERSATION_PROFILE=b2b
   export BRAIN_USE_LLM_NLG=1
   export LLM_PROVIDER=gemini   # or openai
   export GEMINI_API_KEY=...
   export LLM_TEMPERATURE=0.8
   python3 -m uvicorn app.server:app --host 0.0.0.0 --port 8080
   ```
   Then run `cloudflared tunnel run ...` so the public URL is e.g. `wss://voice-agent.yourdomain.com/llm-websocket/{call_id}`.

2. **Set the WebSocket URL and configure the Retell agent** (from repo root):
   ```bash
   export RETELL_AI_KEY="your-retell-api-key"
   export RETELL_LLM_WEBSOCKET_URL="wss://voice-agent.yourdomain.com/llm-websocket"
   python3 scripts/configure_retell_b2b_agent.py --agent-id agent_5d6f2744acfc79e26ddce13af2 --prompt-version v13.3 --custom-llm
   ```
   This updates the agent to BYOM (custom-llm-websocket) with bidirectional mode and keeps the full V13.3 prompt in Retell’s LLM (for hosted fallback). The voice-agent uses the full V13.3 prompt when `B2B_V133_PROMPT_PATH` points to `mcp_servers/b2b_workflow.yaml` (e.g. absolute path or `../../../mcp_servers/b2b_workflow.yaml` when running from `agents/voice-agent/service`).

3. **Verify**
   - **Dashboard**: Retell dashboard → your agent → Response engine: type must be **Custom LLM WebSocket** and `llm_websocket_url` must be your base URL (e.g. `wss://voice-agent.yourdomain.com/llm-websocket`). General prompt should still show V13.3 content (used when falling back to Retell-hosted).
   - **Health**: `curl -s https://voice-agent.yourdomain.com/healthz` → `{"ok":true,"custom_llm_ready":"process"}`.
   - **Test call**: Place a test call; confirm no cutting off, natural flow, and V13.3 emotional tone. Check metrics: `GET /metrics` for `stale_segment_dropped_total`, `ws_write_timeout_total` (should be 0 or low).

## Fallback to Retell-hosted LLM

If the custom LLM path is failing (errors, timeouts, bad behavior):

1. In Retell dashboard, edit the agent and **clear** the WebSocket URL (or set response engine back to Retell LLM).
2. Alternatively, re-run the configure script **without** `--custom-llm` and without `--websocket-url`, then patch the agent so `llm_websocket_url` is empty. The agent will use Retell’s hosted LLM and the same general_prompt (V13.3) already stored on the LLM.

## Monitoring

- **Metrics**: `GET /metrics` (Prometheus). Key counters: `stale_segment_dropped_total`, `ws_write_timeout_total`, `barge_in_cancel_latency_ms`, `keepalive_ping_pong_*`.
- **Structured logs**: Set `WEBSOCKET_STRUCTURED_LOGGING=1` for frame-level JSON logs (high volume).
- **Preflight**: When launching campaigns, if `RETELL_LLM_WEBSOCKET_URL` or `CUSTOM_LLM_HEALTH_URL` is set, preflight includes `custom_llm_probe` (status ok/error/skipped). It is **not** a blocker; launch can proceed and fallback is manual.

## 5 then 20 concurrent

- **5 concurrent**: Single voice-agent process + one Cloudflare tunnel; default queue sizes (256/256) are sufficient.
- **20 concurrent**: Same; ensure host has ~2GB memory for the app. Scale horizontally (multiple tunnel replicas or multiple app replicas behind a single tunnel) for more.
