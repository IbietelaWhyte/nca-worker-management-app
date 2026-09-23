-- ============================================================
-- Migration: Special services
--
-- Some Sundays are bigger than others. The first Sunday of the month carries
-- communion; "Jesus is Lord Service" happens perhaps three times a year. Left to the
-- ordinary rota the same few names land on all of them, because to the planner one
-- Sunday is exactly like the next.
--
-- ONE TABLE WITH A KIND, not two tables. A recurring rule ("first Sunday of every
-- month") and a named one-off are the same thing to every reader of this data - a date
-- that is special and what to call it - and they differ only in how the date is
-- arrived at. That is the shape `availability` and `availability_prompts` already use:
-- a mode column, nullable per-mode columns, and a check constraint per mode. Two tables
-- would mean every query is a union and every screen a merge.
--
-- (day_of_week, week_of_month) WITH -1 MEANING LAST is the smallest encoding that
-- covers first/second/third/fourth/last Sunday: 35 expressible rules and nothing to
-- parse. Fortnightly in the period sense ("every second Sunday") needs an anchor date
-- to count from and is deliberately not expressible - it cannot be said in this
-- vocabulary, which is better than saying it wrong. A fifth occurrence that resolves to
-- no date in a short month is correct rather than an error: there simply was no fifth
-- Sunday that month.
--
-- CHURCH-WIDE AND ADMIN-ONLY. These rules are not scoped to a department: every rota
-- on a matching date is planned as special, in every team. So a head editing "first
-- Sunday" to "second Sunday" would silently change which dates every other department
-- rotates specially - and, because a rota's own snapshot of the name is what the
-- fairness tally counts, would leave already-generated rotas disagreeing with the rule
-- that produced them. Heads read these; only admins write them.
-- ============================================================

create type public.special_service_kind as enum ('recurring', 'one_off');

create table public.special_services (
    id            uuid primary key default gen_random_uuid(),
    name          text not null constraint chk_special_name check (length(trim(name)) > 0),
    kind          public.special_service_kind not null,

    -- Recurring only. 0 = Sunday, matching the convention the rest of the schema uses
    -- (and NOT Python's weekday(), where 0 is Monday - the conversion lives in one
    -- function, rules.py, and this comment is why).
    day_of_week   smallint constraint chk_special_day_of_week check (day_of_week between 0 and 6),
    -- 1-4 are the first four occurrences; -1 is the last, whichever that turns out to
    -- be. 5 is a genuine "fifth Sunday" and resolves to nothing in most months.
    week_of_month smallint constraint chk_special_week_of_month
                  check (week_of_month between 1 and 5 or week_of_month = -1),

    -- One-off only.
    service_date  date,

    is_active     boolean not null default true,
    -- ON DELETE SET NULL: removing the admin who added a rule must not delete the rule.
    -- A nullable column needs an optional Pydantic field, or every read of such a row
    -- raises deep inside a repository.
    created_by    uuid references public.workers(id) on delete set null,
    created_at    timestamptz not null default now(),

    constraint chk_special_recurring check (
        kind <> 'recurring'
        or (day_of_week is not null and week_of_month is not null and service_date is null)
    ),
    constraint chk_special_one_off check (
        kind <> 'one_off'
        or (service_date is not null and day_of_week is null and week_of_month is null)
    )
);

comment on table public.special_services is
    'Dates the church treats as bigger than an ordinary service. Read by the planner, which '
    'keeps a separate fairness tally for them so the same people do not get every big service. '
    'Eligibility is untouched - a special date is staffed from exactly the same roster.';
comment on column public.special_services.week_of_month is
    'Which occurrence in the month: 1-4, 5 for a fifth that most months do not have, or -1 for '
    'the last whichever it is. Null for a one-off.';

-- Partial, because each only applies to its own kind. Neither is an upsert target - an
-- ON CONFLICT arbiter has to be a non-partial index, which is what broke every
-- specific-date availability save with 42P10.
create unique index uq_special_services_rule
    on public.special_services (day_of_week, week_of_month)
    where kind = 'recurring';
create unique index uq_special_services_date
    on public.special_services (service_date)
    where kind = 'one_off';

-- The resolver asks for a window of dates at a time; one-offs are the only kind it can
-- narrow in SQL, rules having no date to compare.
create index idx_special_services_date
    on public.special_services (service_date)
    where kind = 'one_off' and is_active;

alter table public.special_services enable row level security;

-- Heads need to read these: the month preview badges the special dates, which is where
-- a head decides which dates to keep.
create policy "Authenticated users can view special services"
    on public.special_services for select
    to authenticated
    using (true);

-- Church-wide data, so church-wide authority. Mirrored by AdminUser on every write
-- endpoint; keep the two in step.
create policy "Admins can manage special services"
    on public.special_services for all
    using (public.has_app_role('admin'))
    with check (public.has_app_role('admin'));

-- ------------------------------------------------------------
-- Stamp the schedule, do not re-derive it
-- ------------------------------------------------------------

-- The name is snapshotted deliberately. The rota export is a shared artefact and has to
-- keep saying "Jesus is Lord Service" after a rename, and `special_service_name is not
-- null` is the single "was this special" test the fairness tally reads. Re-deriving from
-- the rules instead would mean an admin editing "first Sunday" to "second Sunday"
-- retroactively zeroing everyone's special count - history would change under them.
alter table public.schedules
    add column special_service_id   uuid references public.special_services(id) on delete set null,
    add column special_service_name text,
    add constraint chk_schedule_special check (
        special_service_id is null or special_service_name is not null
    );

comment on column public.schedules.special_service_name is
    'Snapshot of the special service this rota served, or null for an ordinary one. Survives a '
    'rename and survives the rule being deleted (the id is ON DELETE SET NULL), because it is '
    'what the fairness tally counts and what the export prints.';

-- The tally reads history back through the assignment join, so the predicate that
-- matters is "which schedules were special".
create index idx_schedules_special
    on public.schedules (special_service_name)
    where special_service_name is not null;
