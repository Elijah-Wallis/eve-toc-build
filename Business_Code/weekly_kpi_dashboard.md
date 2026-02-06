# Weekly KPI Dashboard (Execution‑Only)

## Purpose
Measure and improve the three physics‑limit rates:
1) **Lead Yield** (good fits per scrape)
2) **Contact Rate** (answers / replies)
3) **Conversion Rate** (booked)

## Weekly Snapshot (Monday)
**Window:** last 7 days (UTC)

### A) Lead Yield
- Total leads ingested
- Good‑fit leads (criteria below)
- Yield = good_fit / total

**Good‑fit rule (v1):**
- rating >= 4.2
- reviews_count >= 15
- phone present

### B) Contact Rate
- Calls placed
- Answered calls
- Answer rate = answered / calls

### C) Conversion Rate
- Booked (GRANTED) outcomes
- Conversion rate = booked / answered

## Data Sources (Supabase)
- `leads`
- `lead_events`
- `call_sessions`
- `segments`

## Example SQL (Supabase)

```sql
-- Total leads ingested
select count(*) from leads
where created_at >= now() - interval '7 days';

-- Good‑fit leads
select count(*) from leads
where created_at >= now() - interval '7 days'
  and rating >= 4.2
  and reviews_count >= 15
  and phone is not null;

-- Calls placed
select count(*) from call_sessions
where created_at >= now() - interval '7 days';

-- Answered calls (example: outcome = 'ANSWERED')
select count(*) from call_sessions
where created_at >= now() - interval '7 days'
  and outcome = 'ANSWERED';

-- Booked (GRANTED)
select count(*) from segments
where last_updated >= now() - interval '7 days'
  and segment = 'GRANTED';
```

## KPI Summary Format
- Lead Yield: X / Y = Z%
- Contact Rate: A / B = C%
- Conversion: M / N = P%

## Weekly Decision
Pick **one** experiment per rate to change next week. Lock winners, drop losers.
