-- ============================================================
-- Migration: Remove assignment confirm/decline
--
-- Asking a worker to confirm or decline never closed a loop. Nothing reassigns a
-- declined slot, so a decline was a status nobody acted on, and the reminder RPC's
-- `status <> 'declined'` predicate meant the one concrete effect of declining was to
-- stop being reminded about a duty still sitting on the rota. Heads chase people by
-- phone either way. Removing the question also removes the false comfort of a
-- dashboard that counted replies nobody was obliged to give.
--
-- What replaces it is not another status. A rota is now judged by how many people are
-- on it against the numbers the department asked for (see the min/max migration that
-- follows this one), which is a fact rather than a tally of answers.
--
-- confirmation_tokens STAYS. It is no longer about confirming anything: it is the
-- per-worker identity behind the public /availability/{token} page, which has no
-- session of its own. Two of its columns go with the feature:
--
--   * assignment_id has been dead since 2026-08-31, when tokens became worker-scoped.
--     It is also about to become dangerous: its FK is ON DELETE CASCADE, and removing
--     a worker from a schedule is about to be a supported edit, so deleting a legacy
--     token holder's assignment would silently delete their token and break their
--     availability link.
--   * last_used_at was only ever written by ConfirmationTokenService.confirm, which
--     goes with this migration. A column nothing writes and nothing reads is a lie.
--
-- pending_reminders (a view superseded by the RPC on the day it was written — it
-- hardcodes a two-day lead time and ignores reminder_days_before) and
-- check_assignment_conflicts (dead since availability filtering moved into Python)
-- are dropped too. The view depends on the status column and would block the drop;
-- both encode a model of the schema that stopped being true.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Drop the dependants, then the column, then the type
-- ------------------------------------------------------------

drop view if exists public.pending_reminders;
drop function if exists public.check_assignment_conflicts(uuid);

-- Both RPCs name public.assignment_status in their return signature, so a
-- `create or replace` cannot shed it. They are recreated in section 3.
drop function if exists public.get_assignments_due_for_notice();
drop function if exists public.get_assignments_due_for_reminder(date);

-- Named for a column that is about to go, but it granted UPDATE on the whole row — a
-- worker could have rewritten their own department_role_id or subteam_id through it.
-- Nothing replaces it: an assignment is edited by a head.
drop policy if exists "Workers can update their own assignment status"
    on public.schedule_assignments;

drop index if exists public.idx_assignments_status;

alter table public.schedule_assignments
    drop column if exists status;

drop type if exists public.assignment_status;

comment on table public.schedule_assignments is
    'Workers assigned to a schedule. Carries no status - a worker is either on the rota or not, '
    'and a head edits it.';

-- ------------------------------------------------------------
-- 2. Trim confirmation_tokens to what the availability link needs
-- ------------------------------------------------------------

drop index if exists public.idx_confirmation_tokens_assignment;

alter table public.confirmation_tokens
    drop column if exists assignment_id,
    drop column if exists last_used_at;

comment on table public.confirmation_tokens is
    'Per-worker public link identity. Backs /availability/{token}, whose visitor has no session, '
    'so the token is what stands in for authentication there. Reused until it expires rather '
    'than consumed. The name is historical - it no longer confirms anything.';

-- ------------------------------------------------------------
-- 3. Both RPCs, minus status
-- ------------------------------------------------------------

-- The notice path has never read reminder_sent_at either, so that column leaves the
-- return signature here rather than in the reminders migration that follows.
create function public.get_assignments_due_for_notice()
returns table (
    id             uuid,
    schedule_id    uuid,
    worker_id      uuid,
    notice_sent_at timestamptz,
    workers        json,
    schedules      json
)
language sql stable as $$
    select
        sa.id,
        sa.schedule_id,
        sa.worker_id,
        sa.notice_sent_at,
        row_to_json(w) as workers,
        row_to_json(s) as schedules
    from public.schedule_assignments sa
    join public.workers   w on w.id = sa.worker_id
    join public.schedules s on s.id = sa.schedule_id
    where
        sa.notice_sent_at is null
        and s.scheduled_date >= current_date
        and w.is_active
        and w.phone is not null
    order by sa.worker_id, s.scheduled_date;
$$;

comment on function public.get_assignments_due_for_notice is
    'Assignments still awaiting their initial "you have been scheduled" SMS, ordered by worker so '
    'the caller can batch a month of dates into one message.';

-- Rewritten again in the multiple-reminders migration. Recreated in its current shape
-- here so this migration leaves a working system on its own.
create function public.get_assignments_due_for_reminder(check_date date)
returns table (
    id               uuid,
    schedule_id      uuid,
    worker_id        uuid,
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
        sa.reminder_sent_at,
        sa.notice_sent_at,
        row_to_json(w) as workers,
        row_to_json(s) as schedules
    from public.schedule_assignments sa
    join public.workers   w on w.id = sa.worker_id
    join public.schedules s on s.id = sa.schedule_id
    where
        sa.reminder_sent_at is null
        and w.is_active
        and w.phone is not null
        and (s.scheduled_date - s.reminder_days_before * interval '1 day')::date = check_date
    order by sa.worker_id, s.scheduled_date;
$$;

comment on function public.get_assignments_due_for_reminder is
    'Assignments whose pre-service reminder falls on check_date.';
