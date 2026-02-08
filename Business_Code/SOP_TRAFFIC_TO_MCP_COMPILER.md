# SOP: Traffic-to-MCP Compiler (Deterministic IP Pipeline)

## Purpose
Convert real outbound API traffic from OpenClaw into reusable MCP tool packages with deterministic generation and verification.

## Owner
Elijah (OpenClaw)

## Scope
- Runtime traffic capture
- MCP package generation per endpoint
- Skills registry updates
- Build and harness verification

## Canonical Components
- Traffic capture hook: `src/runtime/http_traffic.py`
- Runtime integration: `src/runtime/env_loader.py`
- Compiler: `scripts/compile_mcp_from_traffic.py`
- End-to-end runner: `scripts/run_traffic_to_mcp_pipeline.py`
- Generated packages: `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/`
- Generated skill index section: `SKILLS.md`

## Procedure
### 1) Capture Real Traffic
1. Ensure traffic capture is enabled:
   - `OPENCLAW_CAPTURE_TRAFFIC=1` (default on)
2. Execute real runtime paths (Telegram/router/tasks).
3. Confirm `${OPENCLAW_STATE_DIR}/runtime/api_traffic.jsonl` contains records.

### 2) Compile MCP Packages
Run:
```bash
python3 scripts/compile_mcp_from_traffic.py \
  --traffic-file ${OPENCLAW_STATE_DIR}/runtime/api_traffic.jsonl \
  --output-root ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic \
  --skills-file SKILLS.md \
  --manifest-file ${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/manifest.json
```

### 3) Full Pipeline (Preferred)
Run:
```bash
python3 scripts/run_traffic_to_mcp_pipeline.py
```
This performs:
- traffic generation
- MCP generation
- `npm install` and `npm run build` in each generated package
- `client.py` harness execution in isolated venv (`${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/.venv`)

### 4) Verify Success
Check:
- `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/manifest.json`
- `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/pipeline_report.json`
- All tool rows show:
  - `npm_install.returncode = 0`
  - `npm_build.returncode = 0`
  - `client.returncode = 0`

## Security Rules
- Never generate or commit raw secrets from traffic.
- Secret-bearing headers/fields are redacted in traffic capture.
- Use `.env.example` placeholders in generated MCP packages.

## Friction Boundary (Important)
- Canonical logic lives in code (`src/runtime/http_traffic.py`, `scripts/compile_mcp_from_traffic.py`, `scripts/run_traffic_to_mcp_pipeline.py`).
- This SOP is the operational contract; implementation details must be changed in code, not manually rewritten here.

## IP Classification
- This pipeline and its deterministic generators are proprietary process IP.
- Treat compiler scripts + manifests + procedure as enterprise assets.
