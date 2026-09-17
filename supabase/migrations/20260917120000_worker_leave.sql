-- ============================================================
-- Migration: Worker leave
--
-- A worker who is away for a stretch — travelling, on maternity leave, unwell —
-- should drop out of the rota and stop being texted for availability, without
-- anyone having to remember to tick every Sunday individually and without being
-- deactivated (which would remove them from their departments entirely).
--
-- This is a range, not a set of dates, and it is deliberately its own table
-- rather than a pile of rows in `availability`:
--
--   * A range survives being extended. "Back a fortnight later" is one edit here
--     and N inserts-and-deletes there.
--   * The two facts differ in kind. `availability` is a worker's own answer about
--     specific dates; leave is an absence the department agrees to, set by a head,
--     and it is what suppresses the availability prompt. Folding leave into
--     availability would make the prompt suppress itself.
--   * Expanding a range into rows would bake today's service dates into storage,
--     so a schedule added later inside the window would not be covered.
--
-- Overlapping ranges for one worker are rejected in the service rather than by a
-- constraint here: excluding them in Postgres needs btree_gist, and this would be
-- the first extension in the schema. Overlap is untidy rather than harmful — every
-- read unions the rows, so two overlapping leaves still mean "on leave".
-- ============================================================

create table public.worker_leave (
    id          uuid primary key default gen_random_uuid(),
    worker_id   uuid not null references public.workers(id) on delete cascade,

    -- Both ends inclusive: "away 10-20 Oct" is how a person says it, and the
    -- 20th is a day they are still away.
    start_date  date not null,
    end_date    date not null,

    -- Free text, shown to heads only. Never sent anywhere and never texted.
    reason      text,

    -- Nullable by design: ON DELETE SET NULL, so a leave outlives the head who
    -- set it. The Pydantic field must allow None to match.
    created_by  uuid references public.workers(id) on delete set null,
    created_at  timestamptz not null default now(),

    constraint chk_worker_leave_dates check (end_date >= start_date)
);

comment on table public.worker_leave is
    'Stretches a worker is away. Excludes them from schedule generation and from availability prompts.';
comment on column public.worker_leave.end_date is
    'Inclusive. A leave ending on the 20th still covers the 20th.';
comment on column public.worker_leave.reason is
    'Optional note for heads. Never included in any SMS.';

-- Every read is "this worker (or these workers), overlapping this range".
create index idx_worker_leave_worker_dates
    on public.worker_leave (worker_id, start_date, end_date);

-- The daily availability prompt sweep asks "who is away today" across all workers.
create index idx_worker_leave_dates
    on public.worker_leave (start_date, end_date);

alter table public.worker_leave enable row level security;

-- A worker can see their own leave but not set it: leave is agreed with a head,
-- not self-declared. Marking individual dates off is what `availability` is for.
create policy "Workers can view their own leave"
    on public.worker_leave for select
    using (worker_id = public.current_worker_id());

create policy "Admins and department heads can view all leave"
    on public.worker_leave for select
    using (
        public.has_app_role('admin')
        or public.has_app_role('hod')
        or public.has_app_role('assistant_hod')
    );

-- Scoped the way the service scopes it: a head may manage a worker who belongs to
-- a department they oversee, as HOD or as assistant HOD.
create policy "Admins and department heads can manage leave"
    on public.worker_leave for all
    using (
        public.has_app_role('admin')
        or exists (
            select 1
            from public.worker_departments wd
            where wd.worker_id = public.worker_leave.worker_id
              and (
                  public.is_hod(wd.department_id)
                  or exists (
                      select 1
                      from public.department_assistant_hods dah
                      where dah.department_id = wd.department_id
                        and dah.worker_id = public.current_worker_id()
                  )
              )
        )
    );
