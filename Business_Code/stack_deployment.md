# Stack And Deployment Decision (PM2 First, Docker Optional)

## Decision
Default runtime is host-level `pm2` for:
- `openclaw` (gateway)
- `openclaw-runtime` (task loop + cron + queue bridge)
- `openclaw-telegram` (Telegram listener)

Docker is kept as an optional, reproducible harness for:
- local `n8n` (if you ever want cloud independence)
- portable bring-up on a new machine

## Why (Tradeoffs)
PM2-first:
- Lowest RAM and background overhead for a cloud stack (Supabase + cloud n8n).
- Fast iteration and simple debugging (native logs, native filesystem).
- No Docker Desktop daemon, no container image churn.

Docker optional:
- Reproducibility and portability: new machine setup is predictable.
- Isolation: avoids dependency conflicts on the host.
- Best when you want local `n8n` (instead of cloud) or a self-contained dev environment.

## Current Stack Reality
- Supabase is cloud. You do not need local Postgres.
- n8n is cloud. You do not need to run local n8n.
- OpenClaw + runtime loop are already running under PM2.

Conclusion: running Docker continuously is not required and is usually wasted overhead for this setup.

## How To Operate (Minimal)
Check status:
- `pm2 list`
- `pm2 logs openclaw-runtime --lines 50`
- `pm2 logs openclaw-telegram --lines 50`

Restart all:
- `pm2 restart openclaw openclaw-runtime openclaw-telegram --update-env`

## Reclaim Resources (Docker Desktop)
If you are not using Docker for this stack, you can stop it to reclaim RAM, CPU, and background I/O.

Checklist:
1. Stop any running containers: `docker ps` then `docker stop <id>`
2. Stop Docker Desktop (macOS UI): Docker icon in menu bar -> Quit Docker Desktop
3. Prevent auto-start (macOS): System Settings -> General -> Login Items -> disable Docker
4. Verify nothing is running: `docker ps` should be empty (or Docker not running)
5. Optional cleanup: `docker system prune` (removes unused images/volumes)

Note: If you later decide to run local `n8n` via `docker/compose.yaml`, you will need Docker Desktop running again.

## When To Use Docker
Use Docker only if one of these becomes true:
- You want local `n8n` (privacy, reliability, latency, or no cloud dependency).
- You want a single-command bring-up on a new machine.
- You hit host dependency conflicts and want isolation.

Docker entrypoint (optional):
- Compose file: `docker/compose.yaml`

## What Docker Does Here
`docker/compose.yaml` defines two services:
- `n8n`: local n8n with workflow import volume
- `openclaw`: containerized OpenClaw gateway that talks to local n8n via `http://n8n:5678/mcp`

If you do not run `docker compose up`, none of this consumes RAM/CPU.
