-- Full transcript storage for Retell call ingestion
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

-- --- Hardening / invariants (idempotent) ---

-- Guard against empty IDs and physically-impossible values.
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

-- Keep updated_at correct without relying on clients.
create or replace function openclaw_touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end $$;

do $$ begin
  if not exists (
    select 1 from pg_trigger where tgname = 'call_transcripts_touch_updated_at'
  ) then
    create trigger call_transcripts_touch_updated_at
      before update on call_transcripts
      for each row
      execute function openclaw_touch_updated_at();
  end if;
end $$;

-- Fast search: generated tsvector for transcript_text.
alter table call_transcripts
  add column if not exists transcript_tsv tsvector
  generated always as (to_tsvector('simple', coalesce(transcript_text, ''))) stored;

-- Enforce turn.retell_call_id matches transcript.retell_call_id (with a self-healing pre-step).
update call_transcript_turns t
set retell_call_id = ct.retell_call_id
from call_transcripts ct
where t.transcript_id = ct.id
  and t.retell_call_id is distinct from ct.retell_call_id;

-- If any duplicates exist (shouldn't), keep the earliest row and drop the rest so we can enforce a clean upsert key.
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

-- --- Indexes (query paths) ---
-- Note: retell_call_id is already indexed by the UNIQUE constraint on call_transcripts.
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

-- Deterministic read model: reconstruct transcript_text from ordered turns.
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

-- Ensure PostgREST schema cache reflects newly-created tables/columns promptly.
notify pgrst, 'reload schema';
