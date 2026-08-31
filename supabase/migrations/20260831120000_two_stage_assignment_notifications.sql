-- ============================================================
-- Migration: Two-stage assignment notifications
--
-- A worker is now contacted twice about an assignment: once shortly after the
-- schedule is created ("you have been scheduled, please confirm"), and again
-- reminder_days_before the service itself. Previously only the second message
-- existed, so a worker rostered a month ahead by monthly generation first heard
-- about it the night before — too late to arrange cover if they declined.
--
-- Three things have to change for that to work.
--
-- 1. Confirmation tokens were 1:1 with an assignment (unique_assignment_token)
--    and lived 48 hours. Since schedules are created weeks ahead, the token
--    minted for the first message is almost always expired by the time the
--    second one is sent — and minting a replacement violated the unique
--    constraint, an error the caller swallowed, silently sending an SMS with no
--    link. Tokens become worker-scoped instead: one link means "this is you",
--    lists every upcoming duty, and stays usable so a worker can answer one date
--    today and another tomorrow.
--
-- 2. schedule_assignments needs somewhere to record that the first message went
--    out, separate from reminder_sent_at.
--
-- 3. The reminder RPC filtered status = 'pending', which would have excluded
--    anyone who confirmed from the first message — the exact opposite of the
--    intent. It now excludes only workers who declined.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Worker-scoped confirmation tokens
-- ------------------------------------------------------------

alter table public.confirmation_tokens
    drop constraint if exists unique_assignment_token;

-- A worker-scoped token covers every upcoming assignment, so it is no longer
-- tied to one. Kept nullable rather than dropped so links already in flight
-- under the old scheme keep resolving until they expire.
alter table public.confirmation_tokens
    alter column assignment_id drop not null;

-- The token is no longer consumed by its first use: a worker may confirm one
-- date, come back, and decline another. The timestamp is now a record of the
-- most recent use rather than a terminal state.
alter table public.confirmation_tokens
    rename column used_at to last_used_at;

create index if not exists idx_confirmation_tokens_worker
    on public.confirmation_tokens (worker_id);

comment on column public.confirmation_tokens.assignment_id is
    'Legacy: the single assignment a pre-2026-08-31 token was minted for. Null for worker-scoped tokens.';

comment on column public.confirmation_tokens.last_used_at is
    'When the link was last acted on. Not terminal — a worker may return to answer another date.';

-- ------------------------------------------------------------
-- 2. Track the initial notice separately from the reminder
-- ------------------------------------------------------------

alter table public.schedule_assignments
    add column if not exists notice_sent_at timestamptz;

comment on column public.schedule_assignments.notice_sent_at is
    'When the "you have been scheduled" SMS covering this assignment went out. Null means not yet notified.';

-- Mirrors idx_assignments_reminder: the notice job only ever reads the un-notified rows.
create index if not exists idx_assignments_notice
    on public.schedule_assignments (notice_sent_at)
    where notice_sent_at is null;

-- ------------------------------------------------------------
-- 3. RPCs
-- ------------------------------------------------------------

-- Assignments that have been created but not yet announced. Ordered by worker so
-- the caller can group a whole month of dates into a single SMS per person.
create or replace function public.get_assignments_due_for_notice()
returns table (
    id               uuid,
    schedule_id      uuid,
    worker_id        uuid,
    status           public.assignment_status,
    reminder_sent_at timestamptz,
    notice_sent_at   timestamptz,
    workers          json,
    schedules        json
)
language sql stable as $$
    select
        sa.id,
        sa.schedule_id,
        sa.worker_id,
        sa.status,
        sa.reminder_sent_at,
        sa.notice_sent_at,
        row_to_json(w) as workers,
        row_to_json(s) as schedules
    from public.schedule_assignments sa
    join public.workers   w on w.id = sa.worker_id
    join public.schedules s on s.id = sa.schedule_id
    where
        sa.notice_sent_at is null
        and sa.status <> 'declined'
        and s.scheduled_date >= current_date
        and w.is_active
        and w.phone is not null
    order by sa.worker_id, s.scheduled_date;
$$;

comment on function public.get_assignments_due_for_notice is
    'Assignments awaiting their initial "you have been scheduled" SMS, ordered by worker for batching.';

-- Return signature gains notice_sent_at, so the old function must be dropped
-- rather than replaced.
drop function if exists public.get_assignments_due_for_reminder(date);

create function public.get_assignments_due_for_reminder(check_date date)
returns table (
    id               uuid,
    schedule_id      uuid,
    worker_id        uuid,
    status           public.assignment_status,
    reminder_sent_at timestamptz,
    notice_sent_at   timestamptz,
    workers          json,
    schedules        json
)
language sql stable as $$
    select
        sa.id,
        sa.schedule_id,
        sa.worker_id,
        sa.status,
        sa.reminder_sent_at,
        sa.notice_sent_at,
        row_to_json(w) as workers,
        row_to_json(s) as schedules
    from public.schedule_assignments sa
    join public.workers   w on w.id = sa.worker_id
    join public.schedules s on s.id = sa.schedule_id
    where
        sa.reminder_sent_at is null
        -- Was status = 'pending', which silently dropped anyone who had already
        -- confirmed from the initial notice. A confirmed worker still wants the
        -- day-before reminder; only a declined one does not.
        and sa.status <> 'declined'
        -- Previously left to Python, which fetched these rows only to skip them.
        and w.is_active
        and w.phone is not null
        and (s.scheduled_date - s.reminder_days_before * interval '1 day')::date = check_date
    order by sa.worker_id, s.scheduled_date;
$$;

comment on function public.get_assignments_due_for_reminder is
    'Assignments whose pre-service reminder falls on check_date. Excludes declined workers only.';
