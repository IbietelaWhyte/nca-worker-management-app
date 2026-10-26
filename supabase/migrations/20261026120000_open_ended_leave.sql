-- ============================================================
-- Migration: Open-ended leave
--
-- Some absences have no known end — a long illness, a move abroad, a baby.
-- Making a head guess a return date means either picking one far off (and
-- forgetting it is there) or picking one too soon and watching the worker drop
-- back into the rota and start being texted again while still away.
--
-- A NULL end_date now means "until further notice". It stays a range: the
-- leave covers every date from start_date onward until a head records the last
-- day away, which is an update of this row rather than a delete — deleting
-- would erase the history of the absence.
--
-- chk_worker_leave_dates needs no change: `end_date >= start_date` is NULL,
-- not false, when end_date is NULL, and a check constraint only rejects false.
--
-- Every reader's overlap test becomes `end_date >= x OR end_date IS NULL`.
-- The (start_date, end_date) indexes still serve the start_date half.
-- ============================================================

alter table public.worker_leave
    alter column end_date drop not null;

comment on column public.worker_leave.end_date is
    'Inclusive. A leave ending on the 20th still covers the 20th. NULL means no end date yet: it covers every date from start_date on.';
