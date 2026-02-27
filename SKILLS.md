

## Revenue MCP Registry

- `n8n MCP` (remote): `https://elijah-wallis.app.n8n.cloud/mcp-server/http`
  - Required header: `Authorization: Bearer <N8N_MCP_TOKEN>`
  - Expected tools: `search_workflows`, `get_workflow_details`, `execute_workflow`
- `supabase_mcp` (local): `python3 -m mcp_servers.supabase_mcp.server`
  - Tool: `supabase.request`
- `apify_mcp` (local): `python3 -m mcp_servers.apify_mcp.server`
  - Tool: `apify.run_actor`
- `retell_mcp` (local): `python3 -m mcp_servers.retell_mcp.server`
  - Tools: `retell.create_phone_call`, `retell.create_web_call`, `retell.get_call`
- `twilio_mcp` (local): `python3 -m mcp_servers.twilio_mcp.server`
  - Tools: `twilio.send_sms`, `twilio.create_call`
- `intelligence_mcp` (local): `python3 -m mcp_servers.intelligence_mcp.server`
  - Tools: `intelligence.lead_snapshot`, `intelligence.recent_events`
- `cloudflare_mcp` (local): `python3 -m mcp_servers.cloudflare_mcp.server`
  - Tools:
    - `cloudflare.verify_token`
    - `cloudflare.list_zones`
    - `cloudflare.list_tunnels`
    - `cloudflare.create_tunnel`
    - `cloudflare.create_tunnel_token`
    - `cloudflare.upsert_dns_cname`

## Cloudflare Skill (Named Tunnel + DNS, low-friction)

Set once:
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_ZONE_ID`
- `CF_TUNNEL_NAME` (default: `retell-brain`)
- `CF_TUNNEL_HOSTNAME` (example: `ws.example.com`)

Start Cloudflare MCP:
- `python3 -m mcp_servers.cloudflare_mcp.server`

Verify token:
- `curl -sS -X POST http://127.0.0.1:${CLOUDFLARE_MCP_PORT:-7086}/mcp -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"cloudflare.verify_token","arguments":{}}}' | python3 -m json.tool`

Create tunnel + DNS route:
- Create tunnel:
  - `curl -sS -X POST http://127.0.0.1:${CLOUDFLARE_MCP_PORT:-7086}/mcp -H 'Content-Type: application/json' -d "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"cloudflare.create_tunnel\",\"arguments\":{\"name\":\"${CF_TUNNEL_NAME:-retell-brain}\"}}}" | python3 -m json.tool`
- Upsert DNS CNAME:
  - `curl -sS -X POST http://127.0.0.1:${CLOUDFLARE_MCP_PORT:-7086}/mcp -H 'Content-Type: application/json' -d "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"cloudflare.upsert_dns_cname\",\"arguments\":{\"zone_id\":\"${CLOUDFLARE_ZONE_ID}\",\"hostname\":\"${CF_TUNNEL_HOSTNAME}\",\"target\":\"<TUNNEL_ID>.cfargotunnel.com\",\"proxied\":true}}}" | python3 -m json.tool`

Then set websocket URL:
- `RETELL_LLM_WEBSOCKET_URL=wss://${CF_TUNNEL_HOSTNAME}/ws`

## Auto-Generated MCP Skills (Traffic Compiler)

Generated from `${OPENCLAW_STATE_DIR}/runtime/api_traffic.jsonl`.

- `get_workflows`: Get workflows via GET /api/v1/workflows.
  - Path: `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_workflows`
  - Build: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_workflows && npm run build`
  - Verify: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_workflows && python3 client.py`
- `create_webhook`: Create webhook via POST /webhook/{webhook_id}.
  - Path: `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_webhook`
  - Build: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_webhook && npm run build`
  - Verify: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_webhook && python3 client.py`
- `create_resource`: Create resource via POST /{id_id}.
  - Path: `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_resource`
  - Build: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_resource && npm run build`
  - Verify: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_resource && python3 client.py`
- `get_call_sessions`: Get call sessions via GET /rest/v1/call_sessions.
  - Path: `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_call_sessions`
  - Build: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_call_sessions && npm run build`
  - Verify: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_call_sessions && python3 client.py`
- `create_cron_jobs`: Create cron jobs via POST /rest/v1/cron_jobs.
  - Path: `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_cron_jobs`
  - Build: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_cron_jobs && npm run build`
  - Verify: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_cron_jobs && python3 client.py`
- `get_leads`: Get leads via GET /rest/v1/leads.
  - Path: `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_leads`
  - Build: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_leads && npm run build`
  - Verify: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_leads && python3 client.py`
- `get_segments`: Get segments via GET /rest/v1/segments.
  - Path: `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_segments`
  - Build: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_segments && npm run build`
  - Verify: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_segments && python3 client.py`
- `get_task_runs`: Get task runs via GET /rest/v1/task_runs.
  - Path: `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_task_runs`
  - Build: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_task_runs && npm run build`
  - Verify: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_task_runs && python3 client.py`
- `create_task_runs`: Create task runs via POST /rest/v1/task_runs.
  - Path: `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_task_runs`
  - Build: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_task_runs && npm run build`
  - Verify: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_task_runs && python3 client.py`
- `get_tasks`: Get tasks via GET /rest/v1/tasks.
  - Path: `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_tasks`
  - Build: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_tasks && npm run build`
  - Verify: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/get_tasks && python3 client.py`
- `update_tasks`: Update tasks via PATCH /rest/v1/tasks.
  - Path: `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/update_tasks`
  - Build: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/update_tasks && npm run build`
  - Verify: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/update_tasks && python3 client.py`
- `create_tasks`: Create tasks via POST /rest/v1/tasks.
  - Path: `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_tasks`
  - Build: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_tasks && npm run build`
  - Verify: `cd ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/create_tasks && python3 client.py`
