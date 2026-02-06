-- Runtime task engine
create table if not exists tasks (
  id uuid primary key default gen_random_uuid(),
  type text not null,
  payload_json jsonb not null default '{}'::jsonb,
  status text not null default 'queued',
  scheduled_for timestamptz not null default now(),
  retries int not null default 0,
  max_retries int not null default 5,
  locked_by text,
  locked_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists task_runs (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references tasks(id) on delete cascade,
  status text not null,
  started_at timestamptz,
  ended_at timestamptz,
  error text,
  output_json jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_tasks_status_scheduled on tasks(status, scheduled_for);

-- Long-context memory
create table if not exists context_threads (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  status text not null default 'active',
  last_summary text not null default '',
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table if not exists context_events (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid references context_threads(id) on delete cascade,
  event_type text not null,
  payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_context_events_thread on context_events(thread_id, created_at desc);
