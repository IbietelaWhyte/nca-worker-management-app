-- ============================================================
-- Migration: Draft schedules
--
-- Committing a generated month used to make every rota live at once, and within
-- notice_interval_minutes everybody on it was texted "you have been scheduled" -
-- before the head had finished fixing the plan. A month can now be saved as a
-- draft, edited without anybody hearing about it, and finalized when it is right.
-- Finalizing is what tells people.
--
-- finalized_at NULL means draft - the nullable-marker idiom notice_sent_at and
-- attendance_closed_at already use. It defaults to now(), so every existing row
-- and every insert that does not ask for a draft (the single-date generator, a
-- month committed straight to final) is finalized with no code change.
--
-- The two notification RPCs are the single gate: neither returns a row whose
-- schedule is a draft, so no sweep can text about one. Both are replaced with
-- their signatures unchanged; the bodies are copied verbatim from
-- 20260918090000 (notice) and 20260918092000 (reminder), plus the one predicate.
--
-- Drafts still occupy their date (the partial unique indexes are untouched) and
-- still count as booked for other departments and toward fairness: they are the
-- rota somebody intends to publish.
-- ============================================================

alter table public.schedules
    add column finalized_at timestamptz default now(),
    -- ON DELETE SET NULL, so the Pydantic field is optional: a schedule outlives the
    -- head who finalized it.
    add column finalized_by uuid references public.workers(id) on delete set null;

comment on column public.schedules.finalized_at is
    'NULL while the schedule is a draft: nobody on it is texted or shown it. Set when a head finalizes.';

-- The Drafts tab lists one department's drafts across every month.
create index idx_schedules_drafts
    on public.schedules (department_id, scheduled_date)
    where finalized_at is null;

-- ------------------------------------------------------------
-- Notification RPCs: never a draft
-- ------------------------------------------------------------

create or replace function public.get_assignments_due_for_notice()
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
        and s.finalized_at is not null
        and s.scheduled_date >= current_date
        and w.is_active
        and w.phone is not null
    order by sa.worker_id, s.scheduled_date;
$$;

create or replace function public.get_assignments_due_for_reminder(check_date date)
returns table (
    assignment_id uuid,
    schedule_id   uuid,
    worker_id     uuid,
    days_before   smallint,
    workers       json,
    schedules     json
)
language sql stable as $$
    select
        sa.id as assignment_id,
        sa.schedule_id,
        sa.worker_id,
        lead_time.days_before,
        row_to_json(w) as workers,
        row_to_json(s) as schedules
    from public.schedules s
    cross join lateral unnest(s.reminder_days_before) as lead_time(days_before)
    join public.schedule_assignments sa on sa.schedule_id = s.id
    join public.workers              w  on w.id = sa.worker_id
    where
        (s.scheduled_date - lead_time.days_before * interval '1 day')::date = check_date
        and s.finalized_at is not null
        and w.is_active
        and w.phone is not null
        -- Absence of a row is what makes a lead time due. Probes the composite primary
        -- key; there is no second index to keep in step.
        and not exists (
            select 1
            from public.assignment_reminder_sends ars
            where ars.assignment_id = sa.id
              and ars.days_before   = lead_time.days_before
        )
    order by sa.worker_id, s.scheduled_date, lead_time.days_before desc;
$$;

-- ------------------------------------------------------------
-- A worker reading their own assignments directly sees finalized ones only
-- ------------------------------------------------------------

drop policy "Workers can view their own assignments" on public.schedule_assignments;

create policy "Workers can view their own assignments"
    on public.schedule_assignments for select
    to authenticated
    using (
        worker_id = public.current_worker_id()
        and exists (
            select 1
            from public.schedules s
            where s.id = schedule_assignments.schedule_id
              and s.finalized_at is not null
        )
    );
