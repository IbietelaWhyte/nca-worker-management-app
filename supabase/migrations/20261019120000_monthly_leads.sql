-- ============================================================
-- Migration: Monthly leads
--
-- Children's Church names two or three "Teachers of the Month" who are in charge
-- of the department's services for that month. They serve every service in that
-- capacity, so they are shown at the top of the month's schedules and left out of
-- that department's rota generation for the month (still eligible elsewhere: a
-- Teacher of the Month can sing in the choir). Being a lead grants no permission.
--
-- This is its own table rather than a department role or a subteam, because both
-- of those occupy the single slot a worker_departments row has for each:
--
--   * Naming somebody lead would overwrite their real role ("Toddler Teacher") or
--     move them out of their real subteam, which also changes how they are rostered.
--   * Neither carries a month, so a head could not name November's leads in
--     October, and a schedule from March would render whoever holds it today.
--
-- The rows are keyed by month and read live, not stamped onto schedules: nothing
-- derives them from a rule that could later change, so the March rows are the
-- March record and editing them is a correction.
--
-- What a department calls its leads is departments.monthly_lead_title. NULL means
-- the department does not use the feature, so no other team sees the words
-- "Teacher of the Month".
--
-- The cap of three per month is enforced in the service (settings.max_monthly_leads)
-- rather than here: a count constraint across rows needs a trigger, and an extra
-- name is untidy rather than harmful.
-- ============================================================

alter table public.departments
    add column monthly_lead_title text;

comment on column public.departments.monthly_lead_title is
    'What this department calls its monthly leads, e.g. "Teacher of the Month". NULL turns the feature off.';

create table public.monthly_leads (
    id             uuid primary key default gen_random_uuid(),
    department_id  uuid not null references public.departments(id) on delete cascade,
    worker_id      uuid not null references public.workers(id) on delete cascade,

    -- Always the first of the month, so "November 2026" has one spelling.
    month          date not null,

    -- Nullable by design: ON DELETE SET NULL, so a record outlives the head who
    -- set it. The Pydantic field must allow None to match.
    created_by     uuid references public.workers(id) on delete set null,
    created_at     timestamptz not null default now(),

    constraint chk_monthly_leads_first_of_month check (extract(day from month) = 1),
    constraint uq_monthly_leads_department_month_worker unique (department_id, month, worker_id)
);

comment on table public.monthly_leads is
    'Workers a head names to be in charge of a department for one month. Shown on schedules and left out of that month''s rota generation for the department.';
comment on column public.monthly_leads.month is
    'The first day of the month the lead covers.';

-- Every read is "this department, this month".
create index idx_monthly_leads_department_month
    on public.monthly_leads (department_id, month);

alter table public.monthly_leads enable row level security;

-- The names appear at the top of a schedule every worker can open.
create policy "Authenticated users can view monthly leads"
    on public.monthly_leads for select
    to authenticated
    using (true);

-- Scoped the way the service scopes it: an admin, or a head of this department
-- as HOD or as assistant HOD.
create policy "Admins and department heads can manage monthly leads"
    on public.monthly_leads for all
    using (
        public.has_app_role('admin')
        or public.is_hod(public.monthly_leads.department_id)
        or exists (
            select 1
            from public.department_assistant_hods dah
            where dah.department_id = public.monthly_leads.department_id
              and dah.worker_id = public.current_worker_id()
        )
    );
