-- ============================================================
-- Migration: Workers whose number cannot receive texts
--
-- A send that Twilio refused for good - the person replied STOP (21610), the
-- number is invalid (21211) or is not a mobile (21614) - used to be treated
-- like a network blip. The notice was left unmarked, so the sweep tried again
-- every notice_interval_minutes until the duty date passed, and nobody was
-- told the worker had never heard.
--
-- sms_blocked_at NULL means the number is believed reachable - the same
-- nullable-marker idiom as notice_sent_at. SMSService stamps it on every
-- worker with that phone (opt-out belongs to the number, and phone is not
-- unique), and saving a worker's phone clears it.
--
-- Both notification RPCs are replaced with their signatures unchanged; the
-- bodies are copied verbatim from 20261029120000, plus the one predicate.
-- ============================================================

alter table public.workers
    add column sms_blocked_at timestamptz,
    add column sms_error_code integer;

comment on column public.workers.sms_blocked_at is
    'When Twilio permanently refused a text to this number. NULL means reachable. Cleared when the phone is saved.';
comment on column public.workers.sms_error_code is
    'The Twilio error code behind sms_blocked_at, e.g. 21610 (replied STOP).';

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
        and w.sms_blocked_at is null
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
        and w.sms_blocked_at is null
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
