# Eve Health Dashboard

Goal: a "10 second glance" health and system-map view.

## Run

```bash
# Fastest (from anywhere):
eve

# Or:
eve-dashboard

# Health gates (from anywhere):
eve preflight
eve transcripts 168
eve acceptance
eve green 168

# Or from repo root:
bash ${REPO_ROOT}/scripts/dashboard/run_dashboard.sh

# Or from repo root:
python3 scripts/dashboard/health_server.py --open --quiet
```

Open:

```text
http://127.0.0.1:7331
```

## What It Shows

- Green/red checks (fast by default).
- Deep mode includes acceptance gates (can take minutes).
- Bundle selector + Run Ready badge (based on last run of that bundle).
- "What changed since last green" (git diffstat + check deltas).
- Laymen vs Technical vs Split view toggle.
- System map and repo tour links for pitch-deck style navigation.

## Extend

- Add/modify checks in `dashboard/checks.json`.
- Update the system map in `dashboard/system_map.json`.
