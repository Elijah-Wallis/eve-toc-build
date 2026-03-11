-- SSOT Security hardening: enable RLS on public tables and allow access only via service_role JWT.
-- This addresses Supabase Security Advisor 'RLS Disabled in Public' findings while preserving runtime behavior.

-- Core CRM/ops tables
alter table if exists public.leads enable row level security;
alter table if exists public.lead_events enable row level security;
alter table if exists public.call_sessions enable row level security;
alter table if exists public.stoplist enable row level security;
alter table if exists public.segments enable row level security;

-- Runtime orchestration tables
alter table if exists public.tasks enable row level security;
alter table if exists public.task_runs enable row level security;
alter table if exists public.context_threads enable row level security;
alter table if exists public.context_events enable row level security;
alter table if exists public.cron_jobs enable row level security;

-- Transcript tables
alter table if exists public.call_transcripts enable row level security;
alter table if exists public.call_transcript_turns enable row level security;

-- Ontology eventing / integrity tables
alter table if exists public.canonical_outbox enable row level security;
alter table if exists public.applied_events enable row level security;
alter table if exists public.shacl_validation_reports enable row level security;
alter table if exists public.ingest_quarantine enable row level security;

-- Tight policy: only service_role JWT access via PostgREST.
do $$ begin
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='leads' and policyname='leads_service_role_all') then
    create policy leads_service_role_all on public.leads for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='lead_events' and policyname='lead_events_service_role_all') then
    create policy lead_events_service_role_all on public.lead_events for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='call_sessions' and policyname='call_sessions_service_role_all') then
    create policy call_sessions_service_role_all on public.call_sessions for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='stoplist' and policyname='stoplist_service_role_all') then
    create policy stoplist_service_role_all on public.stoplist for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='segments' and policyname='segments_service_role_all') then
    create policy segments_service_role_all on public.segments for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;

  if not exists (select 1 from pg_policies where schemaname='public' and tablename='tasks' and policyname='tasks_service_role_all') then
    create policy tasks_service_role_all on public.tasks for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='task_runs' and policyname='task_runs_service_role_all') then
    create policy task_runs_service_role_all on public.task_runs for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='context_threads' and policyname='context_threads_service_role_all') then
    create policy context_threads_service_role_all on public.context_threads for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='context_events' and policyname='context_events_service_role_all') then
    create policy context_events_service_role_all on public.context_events for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='cron_jobs' and policyname='cron_jobs_service_role_all') then
    create policy cron_jobs_service_role_all on public.cron_jobs for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;

  if not exists (select 1 from pg_policies where schemaname='public' and tablename='call_transcripts' and policyname='call_transcripts_service_role_all') then
    create policy call_transcripts_service_role_all on public.call_transcripts for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='call_transcript_turns' and policyname='call_transcript_turns_service_role_all') then
    create policy call_transcript_turns_service_role_all on public.call_transcript_turns for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;

  if not exists (select 1 from pg_policies where schemaname='public' and tablename='canonical_outbox' and policyname='canonical_outbox_service_role_all') then
    create policy canonical_outbox_service_role_all on public.canonical_outbox for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='applied_events' and policyname='applied_events_service_role_all') then
    create policy applied_events_service_role_all on public.applied_events for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='shacl_validation_reports' and policyname='shacl_validation_reports_service_role_all') then
    create policy shacl_validation_reports_service_role_all on public.shacl_validation_reports for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='ingest_quarantine' and policyname='ingest_quarantine_service_role_all') then
    create policy ingest_quarantine_service_role_all on public.ingest_quarantine for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
end $$;
