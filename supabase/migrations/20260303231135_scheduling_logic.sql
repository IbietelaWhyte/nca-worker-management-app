-- ============================================================
-- Church Worker Management App — Scheduling Logic
-- Run AFTER 001_initial_schema.sql
-- ============================================================

-- ============================================================
-- HELPER VIEW: upcoming assignments needing reminders
-- Returns assignments where:
--   - The schedule is in the future
--   - The reminder has not yet been sent
--   - The worker has a phone number
-- ============================================================
create or replace view public.pending_reminders as
select
    sa.id                  as assignment_id,
    sa.schedule_id,
    sa.worker_id,
    sa.status,
    w.first_name,
    w.phone,
    s.title                as schedule_title,
    s.scheduled_date,
    s.start_time,
    d.name                 as department_name
from public.schedule_assignments sa
join public.workers   w on w.id = sa.worker_id
join public.schedules s on s.id = sa.schedule_id
join public.departments d on d.id = s.department_id
where
    sa.reminder_sent_at is null
    and sa.status != 'declined'
    and w.phone is not null
    and w.is_active = true
    -- Send reminder 2 days before the scheduled date
    and s.scheduled_date = current_date + interval '2 days';

comment on view public.pending_reminders is
    'Assignments due for an SMS reminder — scheduled 2 days out, not yet sent';



-- ============================================================
-- FUNCTION: check_assignment_conflicts(schedule_id)
-- Returns any assignments where the worker marked themselves
-- unavailable on that schedule''s date.
-- Useful to surface warnings in the UI.
-- ============================================================
create or replace function public.check_assignment_conflicts(p_schedule_id uuid)
returns table (
    assignment_id uuid,
    worker_id     uuid,
    first_name    text,
    last_name     text,
    conflict_type text,
    notes         text
)
language sql
stable
as $$
    with schedule_info as (
        select scheduled_date, extract(dow from scheduled_date)::smallint as dow
        from public.schedules
        where id = p_schedule_id
    )
    select
        sa.id          as assignment_id,
        w.id           as worker_id,
        w.first_name,
        w.last_name,
        case
            when a.availability_type = 'specific_date' then 'specific_date_unavailable'
            else 'recurring_unavailable'
        end            as conflict_type,
        a.notes
    from public.schedule_assignments sa
    join public.workers              w  on w.id  = sa.worker_id
    join schedule_info               si on true
    join public.availability         a  on a.worker_id = sa.worker_id
    where
        sa.schedule_id = p_schedule_id
        and a.is_available = false
        and (
            (a.availability_type = 'specific_date' and a.specific_date = si.scheduled_date)
            or
            (a.availability_type = 'recurring'     and a.day_of_week   = si.dow)
        );
$$;

comment on function public.check_assignment_conflicts is
    'Returns workers assigned to a schedule who are marked unavailable on that date';


-- ============================================================
-- USEFUL QUERIES FOR REFERENCE
-- ============================================================

-- Test: check for conflicts on a schedule
-- select * from public.check_assignment_conflicts('d1000000-0000-0000-0000-000000000001');

-- Test: view all pending reminders
-- select * from public.pending_reminders;