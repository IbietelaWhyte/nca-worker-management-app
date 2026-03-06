-- ============================================================
-- Migration: Subteams and Scheduling Configuration
-- Adds:
--   - subteams table (department subgroups e.g. classrooms)
--   - workers_per_slot on departments (default) and subteams (override)
--   - reminder_days_before on schedules
--   - subteam_id on schedule_assignments and worker_departments
-- ============================================================


-- ============================================================
-- DEPARTMENTS — add default workers_per_slot
-- ============================================================
alter table public.departments
    add column workers_per_slot smallint not null default 1
        constraint chk_dept_workers_per_slot check (workers_per_slot > 0);

comment on column public.departments.workers_per_slot is
    'Default number of workers required per slot for this department. Can be overridden at subteam level.';


-- ============================================================
-- SUBTEAMS
-- Subgroups within a department e.g. Toddlers, Juniors, Teens
-- within Children''s Church
-- ============================================================
create table public.subteams (
    id              uuid primary key default gen_random_uuid(),
    department_id   uuid not null references public.departments(id) on delete cascade,
    name            text not null,
    description     text,
    workers_per_slot smallint
        constraint chk_subteam_workers_per_slot check (workers_per_slot > 0),
    created_at      timestamptz not null default now(),
    unique (department_id, name)
);

comment on table public.subteams is
    'Subgroups within a department. workers_per_slot overrides the department default when set.';

comment on column public.subteams.workers_per_slot is
    'Number of workers required per slot. Falls back to department.workers_per_slot when NULL.';


-- ============================================================
-- WORKER DEPARTMENTS — add optional subteam assignment
-- ============================================================
alter table public.worker_departments
    add column subteam_id uuid references public.subteams(id) on delete set null;

comment on column public.worker_departments.subteam_id is
    'Optional subteam the worker belongs to within this department.';


-- ============================================================
-- SCHEDULES — add reminder_days_before and optional subteam
-- ============================================================
alter table public.schedules
    add column reminder_days_before smallint not null default 1
        constraint chk_reminder_days check (reminder_days_before >= 0),
    add column subteam_id uuid references public.subteams(id) on delete set null;

comment on column public.schedules.reminder_days_before is
    'How many days before the scheduled date to send SMS reminders.';

comment on column public.schedules.subteam_id is
    'Optional subteam this schedule is for within the department.';


-- ============================================================
-- SCHEDULE ASSIGNMENTS — add optional subteam
-- ============================================================
alter table public.schedule_assignments
    add column subteam_id uuid references public.subteams(id) on delete set null;

comment on column public.schedule_assignments.subteam_id is
    'Optional subteam the worker is fulfilling in this assignment.';


-- ============================================================
-- INDEXES
-- ============================================================
create index idx_subteams_department on public.subteams(department_id);
create index idx_worker_departments_subteam on public.worker_departments(subteam_id);
create index idx_schedules_subteam on public.schedules(subteam_id);
create index idx_assignments_subteam on public.schedule_assignments(subteam_id);

-- Index to efficiently find schedules needing reminders
create index idx_schedules_reminder on public.schedules(scheduled_date, reminder_days_before);


-- ============================================================
-- RLS
-- ============================================================
alter table public.subteams enable row level security;

create policy "Anyone authenticated can view subteams"
    on public.subteams for select
    using (auth.uid() is not null);

create policy "Admins and department heads can manage subteams"
    on public.subteams for all
    using (
        public.has_app_role('admin')
        or public.is_hod(department_id)
    );