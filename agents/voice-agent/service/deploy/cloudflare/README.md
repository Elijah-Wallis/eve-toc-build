# Cloudflare Deploy (Voice Agent)

This service is a FastAPI WebSocket server. Cloudflare **Tunnel** is the
recommended Cloudflare-native way to expose it without opening inbound ports.

## Dogfood (Local Laptop -> Public URL)

1. Start the service:

```bash
cd agents/voice-agent/service
python3 -m uvicorn app.server:app --host 0.0.0.0 --port 8080
```

2. Install and authenticate `cloudflared`:

```bash
brew install cloudflared
cloudflared tunnel login
```

3. Create a tunnel and route a hostname:

```bash
cloudflared tunnel create voice-agent
cloudflared tunnel route dns voice-agent voice-agent.yourdomain.com
```

4. Create a local config and run it:

```bash
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml <<'YAML'
tunnel: <TUNNEL-UUID>
credentials-file: /Users/$USER/.cloudflared/<TUNNEL-UUID>.json

ingress:
  - hostname: voice-agent.yourdomain.com
    service: http://localhost:8080
    originRequest:
      connectTimeout: 30s
      keepAliveTimeout: 120s
      tcpKeepAlive: 30s
  - service: http_status:404
YAML

cloudflared tunnel run voice-agent
```

Now test:
- Health: `https://voice-agent.yourdomain.com/healthz`
- WebSocket (canonical): `wss://voice-agent.yourdomain.com/llm-websocket/{call_id}`

## Production: 20+ concurrent calls

For **20 concurrent calls** (custom LLM / BYOM), harden as follows:

1. **Origin timeouts** (avoid idle disconnects under load):
   - `connectTimeout: 30s`
   - `keepAliveTimeout: 300s` (5 min; Retell sessions can be long)
   - `tcpKeepAlive: 30s`

2. **No connection limit** at Tunnel level; the voice-agent process uses bounded per-session queues (256 inbound/256 outbound). Run one process per core or scale horizontally.

3. **Resource limits**: Ensure the voice-agent host has enough memory for 20+ WebSocket connections and LLM client buffers (recommend ≥2GB for the app).

4. **Health checks**: Use `/healthz` for liveness. For readiness (custom LLM), call `/healthz` and optionally verify `GET /metrics` returns 200.

5. **Fallback**: If custom LLM path fails, clear the agent’s `llm_websocket_url` in the Retell dashboard so the agent falls back to Retell-hosted LLM.

## Production Pattern (Containers + Tunnel)

Use the included compose file as a reference:
- `docker-compose.tunnel.yml` runs:
  - `voice-agent` container on an internal network
  - `cloudflared` as a sidecar using a **token-based** tunnel (dashboard-managed config)

This pattern scales:
- Run multiple replicas of the stack (VMs/containers) in different regions.
- Cloudflare automatically load balances across active tunnel replicas.
- For 20 concurrent: one replica is sufficient if the host has capacity; scale out for more.

## Notes

- WebSockets are supported through Tunnel. Keepalive is recommended; this service already supports Retell ping/pong.
- Use Cloudflare Access if you want to restrict who can connect during dogfooding.

