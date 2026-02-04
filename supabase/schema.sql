-- OpenClaw v1 ontology-first schema
create extension if not exists pgcrypto;

do $$ begin
  if not exists (select 1 from pg_type where typname = 'call_outcome') then
    create type call_outcome as enum ('GRANTED','STALLED','REVOKED','VOICEMAIL','GATEKEEPER');
  end if;
end $$;

create table if not exists leads (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  place_id text unique,
  business_name text,
  phone text,
  email text,
  website text,
  address text,
  city text,
  state text,
  zip text,
  rating numeric,
  reviews_count integer,
  categories text[],
  status text default 'NEW',
  lead_type text default 'B2B',
  last_contacted_at timestamptz,
  created_at timestamptz default now()
);

create table if not exists lead_events (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid references leads(id) on delete cascade,
  place_id text,
  event_type text not null,
  idempotency_key text unique,
  payload_json jsonb,
  created_at timestamptz default now()
);

create table if not exists call_sessions (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid references leads(id) on delete cascade,
  retell_call_id text unique,
  agent_type text,
  outcome call_outcome,
  duration integer,
  summary text,
  created_at timestamptz default now()
);

create table if not exists stoplist (
  phone text primary key,
  reason text,
  source text,
  created_at timestamptz default now()
);

create table if not exists segments (
  lead_id uuid primary key references leads(id) on delete cascade,
  segment call_outcome,
  last_updated timestamptz default now()
);

create index if not exists leads_phone_idx on leads(phone);
create index if not exists leads_status_idx on leads(status);
create index if not exists lead_events_place_id_idx on lead_events(place_id);
create index if not exists call_sessions_outcome_idx on call_sessions(outcome);
