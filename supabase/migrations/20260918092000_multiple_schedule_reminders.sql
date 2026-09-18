-- ============================================================
-- Migration: Several reminders per schedule
--
-- A rota generated five weeks out and reminded about once, the day before, gives
-- nobody time to arrange cover. Heads want a ladder - a week out, three days out,
-- the night before - set per schedule when it is generated.
--
-- LEAD TIMES are an array on schedules rather than a child table. The set is written
-- once, whole, at generation and read whole; nothing ever asks "which schedules
-- remind at 7 days". A child table would also add a third un-transacted insert to
-- commit_monthly_schedule, whose rollback is already hand-rolled across two. Keeping
-- the column name means the backfill is exact and one line, and a production row of
-- 1 survives as {1}: one reminder, one day before, identical behaviour.
--
-- SEND TRACKING cannot stay on schedule_assignments. "The 7-day one went out, the
-- 3-day one has not" is set membership, and a single nullable timestamp cannot hold
-- it. A marker array could, but only as a read-modify-write that loses a send when
-- two scheduler runs overlap. A row per (assignment, lead time) puts the once-only
-- guarantee in Postgres: the second insert gets 23505 rather than sending a second
-- text.
--
-- The composite primary key is doing three jobs: it is the uniqueness rule, it is the
-- index the RPC's NOT EXISTS probes, and - being a plain rather than a partial unique
-- index - it is a legal ON CONFLICT target, so marking a send is an idempotent upsert.
-- That last distinction is the one that broke every specific-date availability save
-- with 42P10; this is the other side of it.
-- ============================================================

-- ------------------------------------------------------------
-- 1. One row per reminder actually sent
-- ------------------------------------------------------------

create table public.assignment_reminder_sends (
    assignment_id uuid        not null references public.schedule_assignments(id) on delete cascade,
    days_before   smallint    not null constraint chk_reminder_send_days check (days_before >= 0),
    sent_at       timestamptz not null default now(),

    primary key (assignment_id, days_before)
);

comment on table public.assignment_reminder_sends is
    'One row per reminder actually sent. The primary key is what makes a lead time fire once, and '
    'the absence of a row is what makes it due. Replaces schedule_assignments.reminder_sent_at, '
    'which could only say "reminded" or "not reminded".';
comment on column public.assignment_reminder_sends.days_before is
    'Which of the schedule''s lead times this send covered. Deliberately not a foreign key into '
    'that array - the schedule''s ladder can be edited afterwards, and a send that happened stays '
    'happened.';

-- No second index. The primary key is exactly the (assignment_id, days_before) probe the
-- reminder RPC makes, and the table is never scanned any other way.

-- Nobody reads this but the sweep, and nothing in the app renders it: it is a log of what
-- Twilio has already been paid for, not a fact about the rota. Enabled with no policies, so
-- anon and authenticated see nothing and the backend's service-role client is the only writer,
-- exactly as confirmation_tokens does.
alter table public.assignment_reminder_sends enable row level security;

-- Carry the existing marker across, so nobody is re-texted about a date they have
-- already been reminded of. The lead time in force at that moment is the scalar the
-- column still holds - read it before the type change below.
insert into public.assignment_reminder_sends (assignment_id, days_before, sent_at)
select sa.id, s.reminder_days_before, sa.reminder_sent_at
from public.schedule_assignments sa
join public.schedules s on s.id = sa.schedule_id
where sa.reminder_sent_at is not null
on conflict do nothing;

drop index if exists public.idx_assignments_reminder;

alter table public.schedule_assignments
    drop column if exists reminder_sent_at;

-- ------------------------------------------------------------
-- 2. reminder_days_before becomes a set
-- ------------------------------------------------------------

-- Useless once the column is an array - a btree over smallint[] answers no question the
-- RPC asks - and dropping it first avoids a pointless rebuild during the type change.
-- idx_schedules_date already covers the scan the RPC drives off.
drop index if exists public.idx_schedules_reminder;

-- The scalar default and the scalar check both have to go before the cast: Postgres
-- casts the default too, and 1::smallint[] is not a cast.
alter table public.schedules drop constraint if exists chk_reminder_days;
alter table public.schedules alter column reminder_days_before drop default;

alter table public.schedules
    alter column reminder_days_before type smallint[]
    using array[reminder_days_before]::smallint[];

alter table public.schedules
    alter column reminder_days_before set default array[1]::smallint[];

-- Capped at five so a mistyped ladder cannot text a forty-person department forty
-- times. Elements are bounded rather than merely non-negative, because a lead time
-- past a year is a typo. The array_position clause keeps a NULL element out, which
-- the ALL comparisons would otherwise pass over - NULL is not false.
alter table public.schedules
    add constraint chk_reminder_days check (
        cardinality(reminder_days_before) between 0 and 5
        and array_position(reminder_days_before, null) is null
        and 0 <= all (reminder_days_before)
        and 365 >= all (reminder_days_before)
    );

comment on column public.schedules.reminder_days_before is
    'Lead times, in days, at which this schedule''s workers are reminded - {7,3,1} is a week out, '
    'three days out and the night before. Set at generation. An empty array is allowed and means '
    'no reminders at all, only the "you have been scheduled" notice: a real choice for a team that '
    'works off the printed rota, and not one the app should spend their money overriding. '
    'Duplicates are collapsed in Pydantic rather than by a constraint, and would be harmless '
    'anyway - assignment_reminder_sends'' primary key makes the second send a no-op.';

-- ------------------------------------------------------------
-- 3. The RPC returns one row per (assignment, lead time) now due
-- ------------------------------------------------------------

-- The return signature changes shape entirely - a row is no longer an assignment - so
-- the old function has to be dropped rather than replaced.
drop function if exists public.get_assignments_due_for_reminder(date);

create function public.get_assignments_due_for_reminder(check_date date)
returns table (
    assignment_id uuid,
    schedule_id   uuid,
    worker_id     uuid,
    days_before   smallint,
    workers       json,
    schedules     json
)
language sql stable as $$
    select
        sa.id as assignment_id,
        sa.schedule_id,
        sa.worker_id,
        lead_time.days_before,
        row_to_json(w) as workers,
        row_to_json(s) as schedules
    from public.schedules s
    cross join lateral unnest(s.reminder_days_before) as lead_time(days_before)
    join public.schedule_assignments sa on sa.schedule_id = s.id
    join public.workers              w  on w.id = sa.worker_id
    where
        (s.scheduled_date - lead_time.days_before * interval '1 day')::date = check_date
        and w.is_active
        and w.phone is not null
        -- Absence of a row is what makes a lead time due. Probes the composite primary
        -- key; there is no second index to keep in step.
        and not exists (
            select 1
            from public.assignment_reminder_sends ars
            where ars.assignment_id = sa.id
              and ars.days_before   = lead_time.days_before
        )
    order by sa.worker_id, s.scheduled_date, lead_time.days_before desc;
$$;

comment on function public.get_assignments_due_for_reminder is
    'One row per (assignment, lead time) whose reminder falls on check_date. The first column is '
    'assignment_id, not id, because a row is no longer an assignment - the caller must pass '
    'days_before back when marking the send, or the same reminder goes out again tomorrow. The '
    'rename is what forces every caller to be rewritten rather than silently producing duplicates.';
