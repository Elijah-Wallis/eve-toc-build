# One‑Page Operating Cadence (Execution‑Only)

## Monday (Weekly Control Loop)
1) Pull KPI snapshot (last 7 days)
2) Decide 1 experiment per rate:
   - Lead Yield
   - Contact Rate
   - Conversion Rate
3) Schedule experiments and set success thresholds

## Tuesday–Thursday (Execution)
- Run the experiments without changing other variables
- No mid‑week tweaks unless a hard failure is detected

## Friday (Analysis)
- Compare experiment vs baseline
- Keep winners, drop losers
- Update default configs (search strings, call window, scripts)

## Daily (Ops)
- Check `/status`
- Check `/tasks`
- Ensure stoplist respected
- Ensure call window enforced

## Guardrails
- Only change one variable per experiment
- Cap retries and contact attempts
- Do not widen scope mid‑week
