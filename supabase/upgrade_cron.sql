-- Cron jobs table for revenue ops
create table if not exists cron_jobs (
  id uuid primary key default gen_random_uuid(),
  name text unique not null,
  cron text not null,
  task_type text not null,
  payload_json jsonb not null default '{}'::jsonb,
  active boolean not null default true,
  last_run_at timestamptz,
  next_run_at timestamptz,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists idx_cron_jobs_active on cron_jobs(active);
