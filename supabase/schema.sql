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
  decision_maker_confirmed boolean default false,
  dm_email text,
  positive_signal boolean default false,
  touch_count integer default 0,
  first_contacted_at timestamptz,
  last_contacted_at timestamptz,
  next_touch_at timestamptz,
  paused_until timestamptz,
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
create index if not exists leads_next_touch_idx on leads(next_touch_at);
create index if not exists leads_paused_until_idx on leads(paused_until);
create index if not exists lead_events_place_id_idx on lead_events(place_id);
create index if not exists call_sessions_outcome_idx on call_sessions(outcome);

create table if not exists call_transcripts (
  id uuid primary key default gen_random_uuid(),
  call_session_id uuid references call_sessions(id) on delete set null,
  lead_id uuid references leads(id) on delete set null,
  retell_call_id text not null unique,
  source text not null default 'retell',
  campaign_tag text,
  business_name text,
  phone text,
  dm_email text,
  agent_type text,
  retell_call_status text,
  outcome call_outcome,
  summary text,
  transcript_text text not null default '',
  duration_ms bigint,
  recording_url text,
  start_timestamp timestamptz,
  end_timestamp timestamptz,
  payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists call_transcript_turns (
  id bigserial primary key,
  transcript_id uuid not null references call_transcripts(id) on delete cascade,
  retell_call_id text not null,
  turn_index integer not null,
  speaker text not null,
  text text not null,
  start_ms bigint,
  end_ms bigint,
  confidence numeric,
  payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(transcript_id, turn_index)
);

-- Hardening / invariants (idempotent)
do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'call_transcripts_retell_call_id_nonempty') then
    alter table call_transcripts
      add constraint call_transcripts_retell_call_id_nonempty
      check (length(btrim(retell_call_id)) > 0);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'call_transcripts_duration_ms_nonneg') then
    alter table call_transcripts
      add constraint call_transcripts_duration_ms_nonneg
      check (duration_ms is null or duration_ms >= 0);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'call_transcripts_ts_order') then
    alter table call_transcripts
      add constraint call_transcripts_ts_order
      check (start_timestamp is null or end_timestamp is null or end_timestamp >= start_timestamp);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'call_transcript_turns_turn_index_nonneg') then
    alter table call_transcript_turns
      add constraint call_transcript_turns_turn_index_nonneg
      check (turn_index >= 0);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'call_transcript_turns_retell_call_id_nonempty') then
    alter table call_transcript_turns
      add constraint call_transcript_turns_retell_call_id_nonempty
      check (length(btrim(retell_call_id)) > 0);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'call_transcript_turns_speaker_nonempty') then
    alter table call_transcript_turns
      add constraint call_transcript_turns_speaker_nonempty
      check (length(btrim(speaker)) > 0);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'call_transcript_turns_text_nonempty') then
    alter table call_transcript_turns
      add constraint call_transcript_turns_text_nonempty
      check (length(btrim(text)) > 0);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'call_transcript_turns_ms_order') then
    alter table call_transcript_turns
      add constraint call_transcript_turns_ms_order
      check (start_ms is null or end_ms is null or end_ms >= start_ms);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'call_transcript_turns_confidence_range') then
    alter table call_transcript_turns
      add constraint call_transcript_turns_confidence_range
      check (confidence is null or (confidence >= 0 and confidence <= 1));
  end if;
end $$;

create or replace function openclaw_touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end $$;

do $$ begin
  if not exists (select 1 from pg_trigger where tgname = 'call_transcripts_touch_updated_at') then
    create trigger call_transcripts_touch_updated_at
      before update on call_transcripts
      for each row
      execute function openclaw_touch_updated_at();
  end if;
end $$;

alter table call_transcripts
  add column if not exists transcript_tsv tsvector
  generated always as (to_tsvector('simple', coalesce(transcript_text, ''))) stored;

update call_transcript_turns t
set retell_call_id = ct.retell_call_id
from call_transcripts ct
where t.transcript_id = ct.id
  and t.retell_call_id is distinct from ct.retell_call_id;

delete from call_transcript_turns a
using call_transcript_turns b
where a.retell_call_id = b.retell_call_id
  and a.turn_index = b.turn_index
  and a.id > b.id;

create unique index if not exists call_transcripts_id_retell_call_id_uniq on call_transcripts(id, retell_call_id);
create unique index if not exists call_transcript_turns_retell_call_turn_uniq on call_transcript_turns(retell_call_id, turn_index);

do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'call_transcript_turns_transcript_retell_fk') then
    alter table call_transcript_turns
      add constraint call_transcript_turns_transcript_retell_fk
      foreign key (transcript_id, retell_call_id)
      references call_transcripts(id, retell_call_id)
      on delete cascade;
  end if;
end $$;

-- Indexes (query paths)
create index if not exists call_transcripts_campaign_tag_idx on call_transcripts(campaign_tag);
create index if not exists call_transcripts_created_at_idx on call_transcripts(created_at desc);
create index if not exists call_transcripts_lead_id_idx on call_transcripts(lead_id);
create index if not exists call_transcripts_call_session_id_idx on call_transcripts(call_session_id);
create index if not exists call_transcripts_phone_idx on call_transcripts(phone);
create index if not exists call_transcripts_dm_email_idx on call_transcripts(dm_email);
create index if not exists call_transcripts_transcript_tsv_gin on call_transcripts using gin(transcript_tsv);

create index if not exists call_transcript_turns_retell_call_id_idx on call_transcript_turns(retell_call_id);
create index if not exists call_transcript_turns_transcript_id_idx on call_transcript_turns(transcript_id, turn_index);
create index if not exists call_transcript_turns_retell_call_turn_idx on call_transcript_turns(retell_call_id, turn_index);

create or replace view call_transcripts_view as
select
  ct.*,
  coalesce(a.turn_count, 0)::integer as turn_count,
  coalesce(a.turns_json, '[]'::jsonb) as turns_json,
  coalesce(a.transcript_text_from_turns, '') as transcript_text_from_turns,
  coalesce(nullif(ct.transcript_text, ''), a.transcript_text_from_turns, '') as transcript_text_effective
from call_transcripts ct
left join lateral (
  select
    count(*) as turn_count,
    string_agg((t.speaker || ': ' || t.text), E'\n' order by t.turn_index) as transcript_text_from_turns,
    jsonb_agg(
      jsonb_build_object(
        'retell_call_id', t.retell_call_id,
        'turn_index', t.turn_index,
        'speaker', t.speaker,
        'text', t.text,
        'start_ms', t.start_ms,
        'end_ms', t.end_ms,
        'confidence', t.confidence,
        'payload_json', t.payload_json,
        'created_at', t.created_at
      )
      ORDER BY t.turn_index
    ) as turns_json
  from call_transcript_turns t
  where t.transcript_id = ct.id
) a on true;

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
