-- ============================================================
-- Migration: Remove demo seed data
--
-- 20260303184000_seed_data.sql was a migration, so `db push` sent its demo rows to production:
-- five departments, fifteen department roles, twelve fake workers (two with the admin role) and
-- seven schedules from March 2026. That migration is now a no-op and the data lives in seed.sql,
-- which runs locally only. This deletes what an earlier push left behind.
--
-- Deleted by the exact ids the seed used, never by prefix: the local test user in seed.sql is
-- c1000000-...-0000000000ff, and a prefix match would take it too. Children before parents, so
-- nothing relies on a cascade the reader has to look up — though the cascades (app roles,
-- memberships, availability, assignments, subteams) still clear anything attached later.
--
-- On a fresh database this runs before seed.sql and deletes nothing; seed.sql then inserts the
-- demo rows for local development.
-- ============================================================

delete from public.schedules where id in (
    'd1000000-0000-0000-0000-000000000001', 'd1000000-0000-0000-0000-000000000002',
    'd1000000-0000-0000-0000-000000000003', 'd1000000-0000-0000-0000-000000000004',
    'd1000000-0000-0000-0000-000000000005', 'd1000000-0000-0000-0000-000000000006',
    'd1000000-0000-0000-0000-000000000007'
);

delete from public.workers where id in (
    'c1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000002',
    'c1000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000004',
    'c1000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000006',
    'c1000000-0000-0000-0000-000000000007', 'c1000000-0000-0000-0000-000000000008',
    'c1000000-0000-0000-0000-000000000009', 'c1000000-0000-0000-0000-000000000010',
    'c1000000-0000-0000-0000-000000000011', 'c1000000-0000-0000-0000-000000000012'
);

delete from public.department_roles where id in (
    'b1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000002',
    'b1000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000004',
    'b1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000006',
    'b1000000-0000-0000-0000-000000000007', 'b1000000-0000-0000-0000-000000000008',
    'b1000000-0000-0000-0000-000000000009', 'b1000000-0000-0000-0000-000000000010',
    'b1000000-0000-0000-0000-000000000011', 'b1000000-0000-0000-0000-000000000012',
    'b1000000-0000-0000-0000-000000000013', 'b1000000-0000-0000-0000-000000000014',
    'b1000000-0000-0000-0000-000000000015'
);

delete from public.departments where id in (
    'a1000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000002',
    'a1000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000004',
    'a1000000-0000-0000-0000-000000000005'
);
