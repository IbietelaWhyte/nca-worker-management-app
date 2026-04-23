-- ============================================================
-- Create department_assistant_hods table
-- Tracks which workers are assistant HODs for which departments
-- ============================================================

create table public.department_assistant_hods (
    id uuid primary key default gen_random_uuid(),
    worker_id uuid not null references public.workers(id) on delete cascade,
    department_id uuid not null references public.departments(id) on delete cascade,
    assigned_at timestamptz not null default now(),
    unique (worker_id, department_id)
);

comment on table public.department_assistant_hods is 
'Maps assistant HODs to the departments they assist. A worker must have assistant_hod role in worker_app_roles to be listed here.';

comment on column public.department_assistant_hods.worker_id is 
'Worker who is assigned as assistant HOD';

comment on column public.department_assistant_hods.department_id is 
'Department that this assistant HOD assists';

-- Enable RLS
alter table public.department_assistant_hods enable row level security;

-- RLS Policies
create policy "Anyone authenticated can view assistant HOD assignments"
    on public.department_assistant_hods for select
    to authenticated
    using (true);

create policy "Admins can manage assistant HOD assignments"
    on public.department_assistant_hods for all
    to authenticated
    using (
        exists (
            select 1 from public.worker_app_roles war
            join public.workers w on w.id = war.worker_id
            where w.auth_user_id = auth.uid()
            and war.role = 'admin'
        )
    );

create policy "HODs can manage assistant HODs in their departments"
    on public.department_assistant_hods for all
    to authenticated
    using (
        exists (
            select 1 from public.departments d
            join public.workers w on w.id = d.hod_id
            where d.id = department_assistant_hods.department_id
            and w.auth_user_id = auth.uid()
        )
    );

-- Create indexes for common queries
create index idx_department_assistant_hods_worker on public.department_assistant_hods(worker_id);
create index idx_department_assistant_hods_department on public.department_assistant_hods(department_id);
