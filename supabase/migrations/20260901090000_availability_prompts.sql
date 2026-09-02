-- ============================================================
-- Migration: Availability prompts
--
-- Nothing has ever asked a worker to enter their availability. generate_schedule
-- filters on it, so someone who never fills it in is quietly handled by the
-- default and nobody chases them. An HOD can now prompt their department by SMS,
-- either immediately or on a chosen date.
--
-- A scheduled send has to be a row rather than an in-process timer: the app's
-- APScheduler uses the default in-memory jobstore, so a job queued for next month
-- would not survive a restart and would fire once per replica. The daily sweep
-- reads this table instead, following the same nullable-timestamp-as-marker idiom
-- that reminder_sent_at uses on schedule_assignments.
--
-- Also fixes a latent bug this feature would otherwise multiply. The specific-date
-- upsert declares ON CONFLICT (worker_id, day_of_week), but day_of_week is NULL on
-- a specific-date row, and Postgres treats NULLs as distinct — so it never
-- conflicts and inserts a duplicate every single time. The existing frontend hides
-- this by tracking the row id client-side; the new public page cannot.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Make the specific-date upsert actually upsert
-- ------------------------------------------------------------

-- Collapse the duplicates already accumulated, newest wins, so the unique index
-- below can be created.
delete from public.availability a
using public.availability b
where a.availability_type = 'specific_date'
  and b.availability_type = 'specific_date'
  and a.worker_id = b.worker_id
  and a.specific_date = b.specific_date
  and (a.created_at, a.id) < (b.created_at, b.id);

-- WRONG, and superseded by 20260902120000_availability_specific_date_index.sql: this
-- predicate made the index unusable as an ON CONFLICT arbiter (PostgREST cannot send
-- one), so the upsert failed with 42P10 on every call instead of duplicating. It was
-- also unnecessary — recurring rows leave specific_date NULL, so a plain unique index
-- already leaves them unconstrained. Left as-is because this migration has run.
create unique index if not exists uq_availability_worker_specific_date
    on public.availability (worker_id, specific_date)
    where availability_type = 'specific_date';

comment on index public.uq_availability_worker_specific_date is
    'One row per worker per specific date. Backs the ON CONFLICT target of the specific-date upsert.';

-- ------------------------------------------------------------
-- 2. Availability prompts
-- ------------------------------------------------------------

create type public.availability_prompt_mode as enum ('once', 'monthly');

create table public.availability_prompts (
    id              uuid primary key default gen_random_uuid(),
    department_id   uuid not null references public.departments(id) on delete cascade,
    created_by      uuid references public.workers(id) on delete set null,
    mode            public.availability_prompt_mode not null,

    -- Set for 'once'. The sweep picks up anything due on or before today, so a
    -- prompt scheduled while the app was down still goes out on the next run.
    send_on         date,

    -- Set for 'monthly'. Capped at 28 so the day exists in February; a prompt that
    -- silently skipped a month would be worse than one that lands slightly early.
    repeat_day      smallint check (repeat_day between 1 and 28),

    is_active       boolean not null default true,
    last_sent_on    date,
    created_at      timestamptz not null default now(),

    constraint chk_prompt_once check (
        mode <> 'once' or (send_on is not null and repeat_day is null)
    ),
    constraint chk_prompt_monthly check (
        mode <> 'monthly' or (repeat_day is not null and send_on is null)
    )
);

comment on table public.availability_prompts is
    'Scheduled SMS prompts asking a department''s workers to enter their availability.';
comment on column public.availability_prompts.send_on is
    'One-off send date. Null for monthly prompts.';
comment on column public.availability_prompts.repeat_day is
    'Day of month for a monthly prompt, 1-28 so it exists in every month. Null for one-offs.';
comment on column public.availability_prompts.last_sent_on is
    'Date the prompt last went out. Null means never; also what stops a monthly prompt double-sending.';

-- The sweep only ever reads prompts still waiting to go out.
create index idx_availability_prompts_pending
    on public.availability_prompts (department_id)
    where is_active;

alter table public.availability_prompts enable row level security;

create policy "Anyone authenticated can view availability prompts"
    on public.availability_prompts for select
    using (auth.uid() is not null);

create policy "Admins and department heads can manage availability prompts"
    on public.availability_prompts for all
    using (
        public.has_app_role('admin')
        or public.is_hod(department_id)
    );
