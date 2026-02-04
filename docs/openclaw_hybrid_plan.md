# OpenClaw Hybrid Orchestration Plan (Local + Cloud)

## 1) Goal
Build a hybrid swarm where local hardware (Mac Mini M2) orchestrates planning and verification, while cloud workers handle long‑running or parallel tasks. This keeps latency low for daily ops while preserving scalable throughput.

## 2) Core Topology
- **Orchestrator (Local):** Mac Mini M2 runs the OpenClaw gateway, schedulers, and decision logic.
- **Workers (Cloud):** Ephemeral Docker workers execute isolated tasks and report back via event payloads.
- **Source of Truth:** GitHub repo + worktrees for parallel changes.

## 3) Worktree Layout (Local)
```
eve-toc-build/
├─ worktrees/
│  ├─ leadclaw/   # acquisition tasks
│  ├─ opsclaw/    # fulfillment tasks
│  └─ watchclaw/  # monitoring + kill‑switch
├─ docker/
├─ tasks/
└─ docs/
```

## 4) Docker Airlock (Local + Cloud)
- **Local Airlock:** Each agent runs inside its own Docker container for test/verify.
- **Cloud Airlock:** Cloud workers spin ephemeral containers with fixed timeouts.
- **Verification Gate:** Orchestrator merges only after clean health + task results.

## 5) Event‑Driven Communication
**Standard Payload**
```json
{
  "event_id": "evt_YYYYMMDD_HHMMSS_###",
  "event_type": "ops.invoice_autoclaw",
  "source": "worker:opsclaw",
  "timestamp": "ISO-8601",
  "metrics": {
    "latency_ms": 420,
    "cost_usd": 0.12
  },
  "action": {
    "type": "apply_patch",
    "target": "repo",
    "branch": "worktrees/opsclaw"
  }
}
```

## 6) Circuit Breakers
- **Max Iterations:** Hard cap on retries per task.
- **Token Budget:** Per‑task token ceilings to prevent runaway cost.
- **Rate Limit Backoff:** Exponential delays for API errors.
- **Kill Switch:** Stop agent if failure repeats N times.
- **Time Box:** Task-level timeout, enforce container shutdown.

## 7) Stack Recommendations
- **Directory/State:** `eza --tree` + `dust` (if available) for size hotspots.
- **Logs:** JSON logs + `jq` for deterministic queries.
- **Orchestration:** Python asyncio now; migrate to a workflow engine only if scale demands it.

## 8) Migration to Mac Mini M2 (Friday)
1. Install Docker Desktop + OpenClaw dependencies.
2. Clone `eve-toc-build` repo.
3. Copy `.openclaw_env` to the Mac Mini.
4. Start containers with `docker compose --env-file ~/.openclaw_env -f docker/compose.yaml up -d`.
5. Verify with:
   - `openclaw --profile eve gateway health`
   - `openclaw --profile eve cron list`
6. Confirm Telegram delivery from the Mac Mini.

## 9) Validation Checklist
- Gateway health OK.
- Cron jobs scheduled.
- Agent test message delivered.
- Worktree branches isolated and clean.

