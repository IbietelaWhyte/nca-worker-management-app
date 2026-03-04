-- ============================================================
-- Church Worker Management App — Initial Schema Migration
-- Run this in the Supabase SQL editor or via Supabase CLI
-- ============================================================

-- Enable required extensions


-- ============================================================
-- WORKERS
-- Linked to Supabase auth.users via auth_user_id
-- ============================================================
create table public.workers (
    id              uuid primary key default gen_random_uuid(),
    auth_user_id    uuid unique references auth.users(id) on delete set null,
    first_name      text not null,
    last_name       text not null,
    phone           text,
    email           text unique not null,
    is_active       boolean not null default true,
    created_at      timestamptz not null default now()
);

comment on table public.workers is 'Church workers/volunteers who can be scheduled';


-- ============================================================
-- APP ROLES (admin vs hod vs worker)
-- Stored separately from department-level roles
-- ============================================================
create type public.app_role as enum ('admin', 'hod', 'worker');

create table public.worker_app_roles (
    id          uuid primary key default gen_random_uuid(),
    worker_id   uuid not null references public.workers(id) on delete cascade,
    role        public.app_role not null default 'worker',
    unique (worker_id, role)
);

comment on table public.worker_app_roles is 'Application-level roles (admin, hod, worker)';


-- ============================================================
-- DEPARTMENTS
-- e.g. Ushers, Choir, Children Ministry
-- ============================================================
create table public.departments (
    id          uuid primary key default gen_random_uuid(),
    name        text not null unique,
    description text,
    hod_id     uuid references public.workers(id) on delete set null,
    created_at  timestamptz not null default now()
);

comment on table public.departments is 'Church departments or ministries';


-- ============================================================
-- DEPARTMENT ROLES
-- Roles specific to a department, e.g. "Head Usher" in Ushers
-- ============================================================
create table public.department_roles (
    id              uuid primary key default gen_random_uuid(),
    department_id   uuid not null references public.departments(id) on delete cascade,
    name            text not null,
    description     text,
    unique (department_id, name)
);

comment on table public.department_roles is 'Roles within a specific department';


-- ============================================================
-- WORKER DEPARTMENTS (many-to-many)
-- A worker can belong to multiple departments, each with a role
-- ============================================================
create table public.worker_departments (
    id                  uuid primary key default gen_random_uuid(),
    worker_id           uuid not null references public.workers(id) on delete cascade,
    department_id       uuid not null references public.departments(id) on delete cascade,
    department_role_id  uuid references public.department_roles(id) on delete set null,
    joined_at           timestamptz not null default now(),
    unique (worker_id, department_id)
);

comment on table public.worker_departments is 'Maps workers to departments with their department-specific role';


-- ============================================================
-- AVAILABILITY
-- Supports both recurring (day of week) and specific dates
-- ============================================================
create type public.availability_type as enum ('recurring', 'specific_date');

create table public.availability (
    id                  uuid primary key default gen_random_uuid(),
    worker_id           uuid not null references public.workers(id) on delete cascade,
    availability_type   public.availability_type not null,

    -- Used when availability_type = 'recurring'
    day_of_week         smallint check (day_of_week between 0 and 6), -- 0=Sunday

    -- Used when availability_type = 'specific_date'
    specific_date       date,

    is_available        boolean not null default true,
    notes               text,
    created_at          timestamptz not null default now(),

    -- Enforce correct fields per type
    constraint chk_recurring check (
        availability_type != 'recurring' or day_of_week is not null
    ),
    constraint chk_specific_date check (
        availability_type != 'specific_date' or specific_date is not null
    )
);

comment on table public.availability is 'Worker availability - recurring weekly or one-off specific dates';


-- ============================================================
-- SCHEDULES
-- A service or event needing workers, owned by a department
-- ============================================================
create table public.schedules (
    id              uuid primary key default gen_random_uuid(),
    department_id   uuid not null references public.departments(id) on delete cascade,
    title           text not null,
    scheduled_date  date not null,
    start_time      time not null,
    end_time        time not null,
    notes           text,
    created_by      uuid references public.workers(id) on delete set null,
    created_at      timestamptz not null default now(),

    constraint chk_times check (end_time > start_time)
);

comment on table public.schedules is 'A scheduled service or event requiring workers';


-- ============================================================
-- SCHEDULE ASSIGNMENTS
-- Which workers are assigned to a specific schedule
-- ============================================================
create type public.assignment_status as enum ('pending', 'confirmed', 'declined');

create table public.schedule_assignments (
    id                  uuid primary key default gen_random_uuid(),
    schedule_id         uuid not null references public.schedules(id) on delete cascade,
    worker_id           uuid not null references public.workers(id) on delete cascade,
    department_role_id  uuid references public.department_roles(id) on delete set null,
    status              public.assignment_status not null default 'pending',
    reminder_sent_at    timestamptz,
    created_at          timestamptz not null default now(),
    unique (schedule_id, worker_id)
);

comment on table public.schedule_assignments is 'Workers assigned to a schedule with their status';


-- ============================================================
-- INDEXES
-- ============================================================
create index idx_workers_auth_user_id         on public.workers(auth_user_id);
create index idx_workers_is_active            on public.workers(is_active);
create index idx_worker_departments_worker    on public.worker_departments(worker_id);
create index idx_worker_departments_dept      on public.worker_departments(department_id);
create index idx_availability_worker          on public.availability(worker_id);
create index idx_availability_specific_date   on public.availability(specific_date) where availability_type = 'specific_date';
create index idx_schedules_department         on public.schedules(department_id);
create index idx_schedules_date               on public.schedules(scheduled_date);
create index idx_assignments_schedule         on public.schedule_assignments(schedule_id);
create index idx_assignments_worker           on public.schedule_assignments(worker_id);
create index idx_assignments_status           on public.schedule_assignments(status);
create index idx_assignments_reminder         on public.schedule_assignments(reminder_sent_at) where reminder_sent_at is null;


-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================
alter table public.workers               enable row level security;
alter table public.worker_app_roles      enable row level security;
alter table public.departments           enable row level security;
alter table public.department_roles      enable row level security;
alter table public.worker_departments    enable row level security;
alter table public.availability          enable row level security;
alter table public.schedules             enable row level security;
alter table public.schedule_assignments  enable row level security;


-- Helper: get current worker's id from their JWT
create or replace function public.current_worker_id()
returns uuid language sql stable as $$
    select id from public.workers where auth_user_id = auth.uid()
$$;

-- Helper: check if current user has a given app role
create or replace function public.has_app_role(check_role public.app_role)
returns boolean language sql stable as $$
    select exists (
        select 1 from public.worker_app_roles
        where worker_id = public.current_worker_id()
        and role = check_role
    )
$$;

-- Helper: check if current user is head of a given department
create or replace function public.is_hod(dept_id uuid)
returns boolean language sql stable as $$
    select exists (
        select 1 from public.departments
        where id = dept_id
        and hod_id = public.current_worker_id()
    )
$$;


-- WORKERS policies
create policy "Workers can view all active workers"
    on public.workers for select
    using (is_active = true);

create policy "Workers can update their own profile"
    on public.workers for update
    using (auth_user_id = auth.uid());

create policy "Admins can manage all workers"
    on public.workers for all
    using (public.has_app_role('admin'));


-- DEPARTMENTS policies
create policy "Anyone authenticated can view departments"
    on public.departments for select
    using (auth.uid() is not null);

create policy "Admins can manage departments"
    on public.departments for all
    using (public.has_app_role('admin'));


-- DEPARTMENT ROLES policies
create policy "Anyone authenticated can view department roles"
    on public.department_roles for select
    using (auth.uid() is not null);

create policy "Admins and department heads can manage roles"
    on public.department_roles for all
    using (
        public.has_app_role('admin')
        or public.is_hod(department_id)
    );


-- WORKER DEPARTMENTS policies
create policy "Workers can view their own department memberships"
    on public.worker_departments for select
    using (worker_id = public.current_worker_id() or public.has_app_role('admin'));

create policy "Admins and department heads can manage memberships"
    on public.worker_departments for all
    using (
        public.has_app_role('admin')
        or public.is_hod(department_id)
    );


-- AVAILABILITY policies
create policy "Workers can manage their own availability"
    on public.availability for all
    using (worker_id = public.current_worker_id());

create policy "Admins and department heads can view all availability"
    on public.availability for select
    using (
        public.has_app_role('admin')
        or public.has_app_role('hod')
    );


-- SCHEDULES policies
create policy "Anyone authenticated can view schedules"
    on public.schedules for select
    using (auth.uid() is not null);

create policy "Admins and department heads can manage schedules"
    on public.schedules for all
    using (
        public.has_app_role('admin')
        or public.is_hod(department_id)
    );


-- SCHEDULE ASSIGNMENTS policies
create policy "Workers can view their own assignments"
    on public.schedule_assignments for select
    using (worker_id = public.current_worker_id());

create policy "Admins and department heads can manage assignments"
    on public.schedule_assignments for all
    using (
        public.has_app_role('admin')
        or exists (
            select 1 from public.schedules s
            where s.id = schedule_id
            and public.is_hod(s.department_id)
        )
    );

create policy "Workers can update their own assignment status"
    on public.schedule_assignments for update
    using (worker_id = public.current_worker_id());
