-- ============================================================
-- Migration: (formerly) seed data
--
-- This migration used to insert demo departments, roles, workers, availability and schedules.
-- As a migration it ran on `db push`, so production received twelve fake workers — two of them
-- with the admin role. The inserts now live in supabase/seed.sql, which runs on `db reset` only,
-- and 20261020120100_remove_demo_seed_data.sql deletes what an earlier push left behind.
--
-- Left in place as a no-op rather than deleted: production's migration history already records
-- this version, and a missing file would make the local and remote histories disagree.
-- ============================================================

select 1;
