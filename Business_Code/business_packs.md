# Business Scaling Packs

## Pack A — Lead Ops Autonomy
Queue ingestion and dispatch cycles.

```bash
python3 openclaw_cli.py tasks enqueue n8n.trigger '{"workflow":"openclaw-apify-ingest","data":{}}'
python3 openclaw_cli.py tasks enqueue n8n.trigger '{"workflow":"openclaw-retell-dispatch","data":{}}'
python3 openclaw_cli.py tasks enqueue n8n.trigger '{"workflow":"openclaw-nurture-run","data":{}}'
```

## Pack B — Sales Intelligence
Daily KPI snapshot.

```bash
python3 openclaw_cli.py reports --daily
```

## Pack C — Self-Healing
Re-run failed workflows by enqueueing.

```bash
python3 openclaw_cli.py tasks enqueue n8n.trigger '{"workflow":"openclaw-retell-postcall","data":{}}'
```
