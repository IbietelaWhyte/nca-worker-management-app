-- Make the specific-date availability upsert work again.
--
-- 20260901090000_availability_prompts.sql created uq_availability_worker_specific_date as a
-- PARTIAL index (where availability_type = 'specific_date'). That broke every specific-date
-- save with:
--
--     42P10: there is no unique or exclusion constraint matching the ON CONFLICT specification
--
-- Postgres will only use a partial unique index as an ON CONFLICT arbiter if the statement
-- repeats the index predicate, and PostgREST's on_conflict parameter can carry a column list
-- and nothing else — it has no way to express "WHERE availability_type = 'specific_date'".
--
-- The predicate was never needed. Recurring rows leave specific_date NULL, and Postgres treats
-- NULLs as distinct, so a plain unique index already leaves them unconstrained. (This is the
-- opposite of uq_schedules_dept_date_no_subteam, where NULL-distinctness was the problem to work
-- around rather than the behaviour we wanted.)

drop index if exists public.uq_availability_worker_specific_date;

create unique index uq_availability_worker_specific_date
    on public.availability (worker_id, specific_date);

comment on index public.uq_availability_worker_specific_date is
    'One row per worker per specific date. Backs the ON CONFLICT target of the specific-date '
    'upsert, so it must stay non-partial — PostgREST cannot send an index predicate.';
