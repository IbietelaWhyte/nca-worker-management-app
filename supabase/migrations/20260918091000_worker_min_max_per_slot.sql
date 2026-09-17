-- ============================================================
-- Migration: A staffing band instead of one number
--
-- One number per slot forced a false choice. A department that needs four people to
-- run and would happily take six had to pick: set it to four and turn away the fifth
-- and sixth who were free, or set it to six and see every ordinary Sunday flagged
-- understaffed. Splitting it into a minimum and a maximum means "fill up to the
-- maximum when the people are there, and only tell me when we drop below the
-- minimum".
--
-- workers_per_slot is RENAMED to min_workers_per_slot rather than kept alongside a
-- new column, because the minimum is what it already meant: falling short of it is
-- exactly what produced DatePlanStatus.UNDERSTAFFED. Backfilling the maximum to the
-- same value leaves every existing department and subteam behaving precisely as it
-- does today - fill to N, flag below N - until somebody widens it.
--
-- A subteam overrides both bounds or neither (chk_subteam_inherit_both). Per-field
-- inheritance looks more flexible but assembles a contradiction out of two rows: a
-- subteam inheriting a minimum of 3 while overriding its maximum to 2 is impossible,
-- spans two tables, and so cannot be caught by any constraint - it would surface as
-- a rota that is permanently understaffed with nothing on screen to explain it.
-- One toggle in the form, one constraint here.
--
-- The resolved band is also frozen onto each schedule as it is generated, the same
-- way reminder_days_before already is. Every screen that shows a schedule row - the
-- month grid, the schedules table, the dashboard - has the schedule and nothing
-- else in scope, so without this each would have to fetch the department (and the
-- subteams, for a department-wide rota) just to render "3 of 4". Freezing also
-- keeps a March rota honest after the department's numbers change in June: it
-- records what was asked for at the time, not what is asked for now.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Departments: both bounds, always set
-- ------------------------------------------------------------

alter table public.departments rename column workers_per_slot to min_workers_per_slot;
alter table public.departments rename constraint chk_dept_workers_per_slot to chk_dept_min_workers;

-- Added with a default so existing rows satisfy NOT NULL, backfilled to the floor,
-- and only THEN range-checked. Adding chk_dept_worker_range before the backfill
-- would reject every department whose minimum is already above 1 and fail the
-- migration half-applied.
alter table public.departments
    add column max_workers_per_slot smallint not null default 1
        constraint chk_dept_max_workers check (max_workers_per_slot > 0);

update public.departments set max_workers_per_slot = min_workers_per_slot;

alter table public.departments
    add constraint chk_dept_worker_range check (max_workers_per_slot >= min_workers_per_slot);

comment on column public.departments.min_workers_per_slot is
    'Fewest workers a slot can run with. Below this a rota is flagged understaffed. Was '
    'workers_per_slot, which already meant exactly this.';
comment on column public.departments.max_workers_per_slot is
    'Most workers a slot will take when enough are free. Backfilled to the minimum, so an '
    'untouched department behaves exactly as it did before this migration.';

-- ------------------------------------------------------------
-- 2. Subteams: both bounds or neither
-- ------------------------------------------------------------

alter table public.subteams rename column workers_per_slot to min_workers_per_slot;
alter table public.subteams rename constraint chk_subteam_workers_per_slot to chk_subteam_min_workers;

alter table public.subteams
    add column max_workers_per_slot smallint
        constraint chk_subteam_max_workers check (max_workers_per_slot > 0);

update public.subteams set max_workers_per_slot = min_workers_per_slot where min_workers_per_slot is not null;

alter table public.subteams
    add constraint chk_subteam_worker_range check (
        max_workers_per_slot is null or min_workers_per_slot is null
        or max_workers_per_slot >= min_workers_per_slot
    );

-- The rule that makes an impossible resolved band unrepresentable. Without it a
-- subteam could inherit one bound and override the other, and the pair that
-- generation actually uses would live half in this row and half in the department's.
alter table public.subteams
    add constraint chk_subteam_inherit_both check (
        (min_workers_per_slot is null) = (max_workers_per_slot is null)
    );

comment on column public.subteams.min_workers_per_slot is
    'Overrides the department''s minimum. NULL inherits - and then the maximum must be NULL too.';
comment on column public.subteams.max_workers_per_slot is
    'Overrides the department''s maximum. Set together with the minimum or not at all, so a '
    'subteam''s band is never assembled out of two rows.';

-- ------------------------------------------------------------
-- 3. Freeze the resolved band onto each schedule
-- ------------------------------------------------------------

-- Totals across every group the schedule staffs: a department-wide rota that fills
-- three subteams to 2-4 each records 6 and 12, which is what its one row on the
-- month grid has to render. Defaulted rather than NOT NULL because rows created
-- before this migration have no honest answer, and a wrong number is worse than a
-- missing one - the frontend falls back to the assignment count for those.
alter table public.schedules
    add column min_workers smallint
        constraint chk_schedule_min_workers check (min_workers is null or min_workers >= 0),
    add column max_workers smallint
        constraint chk_schedule_max_workers check (max_workers is null or max_workers >= 0),
    add constraint chk_schedule_worker_range check (
        min_workers is null or max_workers is null or max_workers >= min_workers
    );

comment on column public.schedules.min_workers is
    'Staffing floor in force when this schedule was generated, summed across its groups. Frozen '
    'deliberately: a rota generated in March must keep reading correctly after the department''s '
    'numbers change in June. NULL on rows predating the staffing band.';
comment on column public.schedules.max_workers is
    'Staffing ceiling in force when this schedule was generated, summed across its groups. '
    'NULL on rows predating the staffing band.';

-- No index on either. They are only ever read off rows already being fetched.
