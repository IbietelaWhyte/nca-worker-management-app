-- ============================================================
-- Migration: Schedule date uniqueness
--
-- One schedule per (department, date, subteam) was only ever enforced in the
-- application (ScheduleService.generate_schedule's get_existing_schedule check),
-- which leaves a race between the check and the insert. Monthly generation widens
-- that window considerably: the HOD reviews a preview, then commits a whole month
-- of rows in one statement.
--
-- Two partial indexes are needed rather than one plain unique constraint, because
-- Postgres treats NULLs as distinct — a single index on
-- (department_id, scheduled_date, subteam_id) would not stop two department-level
-- schedules (subteam_id IS NULL) landing on the same date.
--
-- These also serve the month view's (department_id, scheduled_date) range scan,
-- which previously had no composite index.
-- ============================================================

-- Subteam-level schedules: one per subteam per date.
create unique index if not exists uq_schedules_dept_date_subteam
    on public.schedules (department_id, scheduled_date, subteam_id)
    where subteam_id is not null;

-- Department-level schedules: one per department per date. This matches the
-- application's duplicate check, where DEPARTMENT_ONLY and DEPARTMENT_ALL share
-- the subteam_id IS NULL key.
create unique index if not exists uq_schedules_dept_date_no_subteam
    on public.schedules (department_id, scheduled_date)
    where subteam_id is null;

comment on index public.uq_schedules_dept_date_subteam is
    'One schedule per subteam per date. Backs the application-level duplicate check.';

comment on index public.uq_schedules_dept_date_no_subteam is
    'One department-level schedule per date. NULL subteam_id needs its own partial index because NULLs compare as distinct.';
