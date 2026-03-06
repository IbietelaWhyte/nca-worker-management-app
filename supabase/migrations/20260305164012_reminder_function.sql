-- ============================================================
-- Migration: Reminder RPC function
-- Called by FastAPI's ReminderService to find assignments
-- due for SMS reminders on a given date
-- ============================================================

create or replace function public.get_assignments_due_for_reminder(check_date date)
returns table (
    id              uuid,
    schedule_id     uuid,
    worker_id       uuid,
    status          public.assignment_status,
    reminder_sent_at timestamptz,
    workers         json,
    schedules       json
)
language sql stable as $$
    select
        sa.id,
        sa.schedule_id,
        sa.worker_id,
        sa.status,
        sa.reminder_sent_at,
        row_to_json(w)  as workers,
        row_to_json(s)  as schedules
    from public.schedule_assignments sa
    join public.workers   w on w.id = sa.worker_id
    join public.schedules s on s.id = sa.schedule_id
    where
        sa.reminder_sent_at is null
        and sa.status = 'pending'
        and (s.scheduled_date - s.reminder_days_before * interval '1 day')::date = check_date;
$$;