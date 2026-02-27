-- Phase patch: Supabase-first outbox + machine-actionable SHACL artifacts

create table if not exists canonical_outbox (
  event_id text primary key,
  mutation_key text not null,
  aggregate_type text not null,
  aggregate_id text not null,
  schema_version integer not null default 1,
  entity_key text not null,
  payload_delta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  published_at timestamptz
);

create index if not exists canonical_outbox_created_idx on canonical_outbox(created_at);
create index if not exists canonical_outbox_published_idx on canonical_outbox(published_at);

create table if not exists applied_events (
  id bigserial primary key,
  event_id text not null,
  consumer_name text not null,
  applied_at timestamptz not null default now(),
  unique(event_id, consumer_name)
);

create index if not exists applied_events_event_id_idx on applied_events(event_id);

create table if not exists shacl_validation_reports (
  id uuid primary key default gen_random_uuid(),
  event_id text not null,
  report_schema_version text not null,
  failure_code text not null check (failure_code <> 'validation_failed'),
  missing_predicates text[] not null default '{}'::text[],
  provenance_pointers text[] not null default '{}'::text[],
  report_payload jsonb not null default '{}'::jsonb,
  report_hash text not null,
  created_at timestamptz not null default now()
);

create index if not exists shacl_validation_reports_event_id_idx on shacl_validation_reports(event_id);

create table if not exists ingest_quarantine (
  id uuid primary key default gen_random_uuid(),
  event_id text not null,
  report_schema_version text not null,
  failure_code text not null check (failure_code <> 'validation_failed'),
  missing_predicates text[] not null default '{}'::text[],
  provenance_pointers text[] not null default '{}'::text[],
  quarantine_payload jsonb not null default '{}'::jsonb,
  report_hash text not null,
  created_at timestamptz not null default now()
);

create index if not exists ingest_quarantine_event_id_idx on ingest_quarantine(event_id);
