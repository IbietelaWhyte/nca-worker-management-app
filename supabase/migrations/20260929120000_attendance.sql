-- ============================================================
-- Migration: Attendance / attendance
--
-- A rota says who was asked. Nothing has ever said who came. Heads know their repeat
-- absentees by memory, which means they know the loud ones and not the quiet ones, and a
-- department loses somebody three months after they stopped turning up.
--
-- THIS IS NOT THE STATUS COLUMN COMING BACK. 20260918090000 dropped
-- schedule_assignments.status because it was a question put to a worker about the future
-- that nothing acted on: a decline reassigned nobody, and its one concrete effect was to
-- cancel a reminder for a duty still sitting on the rota. Attendance is the opposite in
-- every respect - an observation, recorded by whoever ran the service, about a date that
-- has already happened, feeding a report a head can act on. That migration's own words
-- were "what replaces it is not another status ... which is a fact rather than a tally of
-- answers". This is a fact, and it is recorded by the operator, never by the worker.
--
-- ABSENCE IS STAMPED AT CLOSURE, NEVER DERIVED, and this is the load-bearing decision.
-- The cheaper design is checked_in_at alone, with absence derived as "attendance closed
-- and this one is null". It is wrong, because add_assignment and replace_assignment_worker
-- are supported edits: a head who closes Sunday's attendance and on Tuesday adds the person
-- who actually served would create a row with no check-in against a closed attendance, and
-- that person would be recorded absent from a service they attended. Deriving moves the
-- "false absence" hazard from forgetting to editing, where it is silent and lands on
-- exactly the wrong person.
--
-- So closing attendance is an event that stamps marked_absent_at, and it is the only
-- writer of it. A rota nobody closed has no absences by construction rather than by a
-- predicate a later query can forget, and a row added after closure reads "not recorded"
-- rather than acquiring an absence nobody observed.
--
-- THREE STATES, TWO TIMESTAMPS, NO ENUM:
--     checked_in_at null, marked_absent_at null -> not recorded
--     checked_in_at set,  marked_absent_at null -> present
--     checked_in_at null, marked_absent_at set  -> absent
-- The pair is mutually exclusive by check constraint rather than by convention.
-- ============================================================

-- ------------------------------------------------------------
-- 1. What happened to each person on the rota
-- ------------------------------------------------------------

alter table public.schedule_assignments
    add column checked_in_at    timestamptz,
    -- ON DELETE SET NULL, like schedules.created_by: removing the head who took the roll
    -- call must not delete the record of who turned up. A nullable column needs an
    -- optional Pydantic field on the way back.
    add column checked_in_by    uuid references public.workers(id) on delete set null,
    add column marked_absent_at timestamptz,
    -- Whole minutes after the service's start_time. Null means nobody judged it: a
    -- correction entered days later says nothing about when they arrived, and a zero there
    -- would read as "on time" for somebody nobody saw arrive.
    add column minutes_late     smallint,
    -- STAMPED, not compared on read. The grace period is one global setting, and
    -- re-deriving lateness would mean widening it in June quietly un-lating every March
    -- service and rewriting a report a head has already acted on. Freezing the judgement
    -- is the stance schedules.min_workers and special_service_name already take.
    add column is_late          boolean not null default false,
    -- An absence that should not count. Stamped at closure when worker_leave already
    -- covers the date: leave never edits the rota, so somebody away is still on it and
    -- would otherwise be marked absent for a fortnight they agreed with their head. A head
    -- can also set it afterwards.
    add column excused          boolean not null default false,

    -- Present and absent are the two answers to one question, so a row cannot hold both.
    add constraint chk_attendance_exclusive check (
        checked_in_at is null or marked_absent_at is null
    ),
    -- Lateness is a property of an arrival, and it cannot be claimed without the number
    -- behind it.
    add constraint chk_attendance_late_needs_arrival check (
        not is_late or checked_in_at is not null
    ),
    add constraint chk_attendance_late_needs_minutes check (
        not is_late or minutes_late is not null
    ),
    add constraint chk_attendance_minutes_need_arrival check (
        minutes_late is null or checked_in_at is not null
    ),
    add constraint chk_attendance_minutes_non_negative check (
        minutes_late is null or minutes_late >= 0
    ),
    add constraint chk_attendance_recorder_needs_arrival check (
        checked_in_by is null or checked_in_at is not null
    ),
    -- Excusing is about absences, so "excused" keeps exactly one meaning.
    add constraint chk_attendance_excused_is_absence check (
        not excused or marked_absent_at is not null
    );

comment on column public.schedule_assignments.checked_in_at is
    'When the operator marked this worker present. Null alone is NOT absence - see '
    'marked_absent_at. A worker can never write this: there is no self-service path, by design.';
comment on column public.schedule_assignments.marked_absent_at is
    'When closing attendance recorded this worker as not having turned up. Written only by '
    'close_attendance and cleared only by reopening it, which is what makes "attendance nobody '
    'closed records nothing" true by construction rather than by a predicate.';
comment on column public.schedule_assignments.minutes_late is
    'Minutes after the service start_time, or null when the check-in did not happen on the '
    'service day - a tap on Tuesday says nothing about Sunday morning.';
comment on column public.schedule_assignments.is_late is
    'Whether minutes_late beat the grace period IN FORCE AT THE TAP. Stored rather than compared '
    'on read so that widening settings.attendance_grace_minutes cannot rewrite history.';
comment on column public.schedule_assignments.excused is
    'This absence does not count against the worker. Stamped at closure from worker_leave, and '
    'settable by a head afterwards. Excluded from the absence tally, kept in the duty count.';

-- The attendance screen and the absence report both ask "who has been checked in", and the
-- report scans a department's month. Partial because the interesting rows are the minority
-- early on, matching idx_assignments_notice.
create index idx_assignments_checked_in
    on public.schedule_assignments (checked_in_at)
    where checked_in_at is not null;

create index idx_assignments_absent
    on public.schedule_assignments (marked_absent_at)
    where marked_absent_at is not null;

-- ------------------------------------------------------------
-- 2. Closing attendance is a fact about the schedule
-- ------------------------------------------------------------

-- Two columns rather than an attendance_sessions table: there is exactly one per rota and
-- it has no fields beyond when and who, so a 1:1 table would be a join on every schedule
-- read for two scalars. A nullable timestamp as the marker is the idiom notice_sent_at and
-- availability_prompts.last_sent_on already use, and ScheduleResponse already carries the
-- schedule to every screen that would render this.
--
-- ONE REGISTER PER SERVICE, not per subteam. A department-wide rota is one schedules row
-- covering several subteams, and one person stands at the door and closes it once for
-- everybody. Putting the marker on a finer grain would mean a service could be half
-- recorded with no way to say so.
alter table public.schedules
    add column attendance_closed_at timestamptz,
    add column attendance_closed_by uuid references public.workers(id) on delete set null,
    add constraint chk_attendance_closed_by check (
        attendance_closed_by is null or attendance_closed_at is not null
    );

comment on column public.schedules.attendance_closed_at is
    'When the operator finished marking who turned up. Null means attendance was never taken, '
    'which is NOT the same as everybody being absent - nothing is recorded for this rota at all, '
    'deliberately, because forgetting must never manufacture absences.';

-- The absence report asks exactly (department, date window). Two single-column indexes
-- make the planner pick one and filter the rest.
create index idx_schedules_dept_date on public.schedules (department_id, scheduled_date);

-- ------------------------------------------------------------
-- 3. RLS
--
-- No new policies are needed for the columns themselves: RLS is row-level, so they inherit
-- schedule_assignments' existing "Workers can view their own assignments" (a worker seeing
-- they were marked absent is right) and "Admins and department heads can manage
-- assignments" (an operator writing it is right). The policy that would have let a worker
-- write their own was already dropped by 20260918090000, whose comment reads "Nothing
-- replaces it: an assignment is edited by a head." Do not recreate anything shaped like it.
--
-- Closing attendance is an UPDATE on schedules, and an assistant HOD may do it. The
-- existing manage policy only knows is_hod(), which reads departments.hod_id alone - so RLS
-- has been narrower than the app since assistant HODs were added, invisible until now
-- because the backend uses the service-role client and bypasses RLS entirely. Closing that
-- gap here for the role that will be taking most attendances, since CLAUDE.md asks the two
-- be kept in step.
-- ------------------------------------------------------------

create policy "Assistant heads can manage their departments' schedules"
    on public.schedules for all
    using (
        exists (
            select 1
            from public.department_assistant_hods dah
            where dah.department_id = public.schedules.department_id
              and dah.worker_id = public.current_worker_id()
        )
    );
