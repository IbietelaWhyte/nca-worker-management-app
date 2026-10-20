-- ============================================================
-- Local bootstrap: one admin you can actually sign in as.
--
-- `20260303184000_seed_data.sql` gives a local stack twelve workers, five departments and a
-- month of rotas, but no auth.users rows and every auth_user_id null - so the whole RLS
-- chain (auth.uid() -> workers.auth_user_id -> workers.id -> worker_app_roles) resolves to
-- nothing and there is nobody to log in as. This closes that.
--
-- Run automatically by `supabase db reset` and the first `supabase start`, via
-- [db.seed] in config.toml. It is NEVER run by `supabase db push`, so it cannot reach a
-- hosted project - which is why a known password in a tracked file is safe here and would
-- not be in a migration.
--
-- Three rows, because signing in needs all three:
--   auth.users       - the credential GoTrue checks
--   auth.identities  - the email-provider row the password grant resolves through
--   public.workers   - the profile every authorization decision actually reads
--
-- Fixed UUIDs and ON CONFLICT DO NOTHING throughout, so re-running changes nothing.
-- ============================================================

-- Literals rather than \set: the CLI sends this file to the server as a batch, not
-- through psql, so meta-commands are a syntax error. e1000000-… keeps the auth id clear
-- of the seed migration's c1000000-… worker block.

insert into auth.users (
    id,
    instance_id,
    aud,
    role,
    email,
    encrypted_password,
    email_confirmed_at,
    created_at,
    updated_at,
    raw_app_meta_data,
    raw_user_meta_data,
    -- Empty strings, not NULL. These four have no default, and GoTrue scans them into plain
    -- Go strings — a NULL makes every sign-in fail with "Database error querying schema",
    -- which names neither the column nor the row. The other token columns already default
    -- to ''. This is the single reason a hand-written auth.users row usually does not work.
    confirmation_token,
    recovery_token,
    email_change,
    email_change_token_new
) values (
    'e1000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000000',
    'authenticated',
    'authenticated',
    'test_user@test.com',
    -- pgcrypto lives in the `extensions` schema, which a plain psql search_path does not
    -- include - hence the qualification. bcrypt because that is what GoTrue verifies with.
    extensions.crypt('TestUserPassword123!', extensions.gen_salt('bf')),
    -- Confirmed on the spot. config.toml disables confirmations locally anyway, but a null
    -- here makes the password grant refuse the sign-in.
    now(),
    now(),
    now(),
    -- `role` is the only claim the backend reads for authorization: GoTrue copies
    -- raw_app_meta_data into the JWT's app_metadata, and core/authentication.py takes it
    -- from there. Without it this account signs in successfully and can do nothing.
    '{"provider":"email","providers":["email"],"role":"admin"}'::jsonb,
    '{}'::jsonb,
    '',
    '',
    '',
    ''
)
on conflict (id) do nothing;
-- Note: confirmed_at is a generated column. Inserting into it is an error, not an option.

-- GoTrue looks an email/password user up through its identity row, not through auth.users
-- directly. Without this the account exists and cannot log in.
insert into auth.identities (
    id,
    provider_id,
    user_id,
    identity_data,
    provider,
    created_at,
    updated_at
) values (
    gen_random_uuid(),
    -- For the email provider this is the user's own id, as text.
    'e1000000-0000-0000-0000-000000000001',
    'e1000000-0000-0000-0000-000000000001',
    '{"sub": "e1000000-0000-0000-0000-000000000001", "email": "test_user@test.com", "email_verified": true, "phone_verified": false}'::jsonb,
    'email',
    now(),
    now()
)
on conflict (provider_id, provider) do nothing;

-- The profile. auth.users says who signed in; this says what they may do, and the email
-- matches the login because that is the invariant create_account_for_worker maintains.
insert into public.workers (id, auth_user_id, first_name, last_name, email, phone, is_active)
values ('c1000000-0000-0000-0000-0000000000ff', 'e1000000-0000-0000-0000-000000000001', 'Test', 'User', 'test_user@test.com', '+14165550100', true)
on conflict (id) do nothing;

insert into public.worker_app_roles (worker_id, role)
values ('c1000000-0000-0000-0000-0000000000ff', 'admin')
on conflict (worker_id, role) do nothing;


-- ============================================================
-- DEMO DATA (local only)
--
-- Five departments, their roles, twelve workers and a fortnight of rotas, so a fresh local stack
-- has something to schedule. This used to be the migration 20260303184000_seed_data.sql, which
-- meant `db push` sent fake workers — two of them admins — to production. Kept here instead,
-- because seed.sql runs on `db reset` and never on push.
-- ============================================================

-- ============================================================
-- DEPARTMENTS
-- ============================================================
insert into public.departments (id, name, description) values
    ('a1000000-0000-0000-0000-000000000001', 'Ushers',              'Welcomes and directs congregation members'),
    ('a1000000-0000-0000-0000-000000000002', 'Choir',               'Leads musical worship during services'),
    ('a1000000-0000-0000-0000-000000000003', 'Children''s Ministry', 'Oversees children''s programs and Sunday school'),
    ('a1000000-0000-0000-0000-000000000004', 'Technical',            'Manages sound, lighting, and projection'),
    ('a1000000-0000-0000-0000-000000000005', 'Prayer Team',         'Leads intercessory prayer during services');


-- ============================================================
-- DEPARTMENT ROLES
-- ============================================================
insert into public.department_roles (id, department_id, name, description) values
    -- Ushers
    ('b1000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'Head Usher',    'Coordinates the usher team'),
    ('b1000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000001', 'Floor Usher',   'Guides congregation to seats'),
    ('b1000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000001', 'Door Usher',    'Manages entrance doors'),
    -- Choir
    ('b1000000-0000-0000-0000-000000000004', 'a1000000-0000-0000-0000-000000000002', 'Choir Director','Leads and rehearses the choir'),
    ('b1000000-0000-0000-0000-000000000005', 'a1000000-0000-0000-0000-000000000002', 'Alto',          'Alto vocal section'),
    ('b1000000-0000-0000-0000-000000000006', 'a1000000-0000-0000-0000-000000000002', 'Soprano',       'Soprano vocal section'),
    ('b1000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000002', 'Tenor',         'Tenor vocal section'),
    -- Children's Ministry
    ('b1000000-0000-0000-0000-000000000008', 'a1000000-0000-0000-0000-000000000003', 'Ministry Lead', 'Oversees all children programs'),
    ('b1000000-0000-0000-0000-000000000009', 'a1000000-0000-0000-0000-000000000003', 'Teacher',       'Teaches Sunday school class'),
    ('b1000000-0000-0000-0000-000000000010', 'a1000000-0000-0000-0000-000000000003', 'Assistant',     'Supports teachers'),
    -- Technical
    ('b1000000-0000-0000-0000-000000000011', 'a1000000-0000-0000-0000-000000000004', 'Technical Lead',       'Oversees all technical operations'),
    ('b1000000-0000-0000-0000-000000000012', 'a1000000-0000-0000-0000-000000000004', 'Sound Engineer','Manages the soundboard'),
    ('b1000000-0000-0000-0000-000000000013', 'a1000000-0000-0000-0000-000000000004', 'Projectionist', 'Manages slides and projection'),
    -- Prayer Team
    ('b1000000-0000-0000-0000-000000000014', 'a1000000-0000-0000-0000-000000000005', 'Prayer Lead',   'Leads the prayer team'),
    ('b1000000-0000-0000-0000-000000000015', 'a1000000-0000-0000-0000-000000000005', 'Intercessor',   'Participates in intercessory prayer');


-- ============================================================
-- WORKERS (test profiles — no auth_user_id)
-- ============================================================
insert into public.workers (id, first_name, last_name, email, phone, is_active) values
    ('c1000000-0000-0000-0000-000000000001', 'Samuel',   'Adeyemi',   'samuel.adeyemi@example.com',   '+14165550101', true),
    ('c1000000-0000-0000-0000-000000000002', 'Grace',    'Okonkwo',   'grace.okonkwo@example.com',    '+16475550102', true),
    ('c1000000-0000-0000-0000-000000000003', 'Daniel',   'Mensah',    'daniel.mensah@example.com',    '+14375550103', true),
    ('c1000000-0000-0000-0000-000000000004', 'Esther',   'Nwosu',     'esther.nwosu@example.com',     '+14165550104', true),
    ('c1000000-0000-0000-0000-000000000005', 'Joshua',   'Boateng',   'joshua.boateng@example.com',   '+16475550105', true),
    ('c1000000-0000-0000-0000-000000000006', 'Mary',     'Eze',        'mary.eze@example.com',         '+14375550106', true),
    ('c1000000-0000-0000-0000-000000000007', 'Emmanuel', 'Asante',    'emmanuel.asante@example.com',  '+16045550107', true),
    ('c1000000-0000-0000-0000-000000000008', 'Ruth',     'Osei',       'ruth.osei@example.com',        '+17785550108', true),
    ('c1000000-0000-0000-0000-000000000009', 'Peter',    'Nkemdirim', 'peter.nkemdirim@example.com',  '+16045550109', true),
    ('c1000000-0000-0000-0000-000000000010', 'Abigail',  'Darko',     'abigail.darko@example.com',    '+17785550110', true),
    ('c1000000-0000-0000-0000-000000000011', 'Isaac',    'Owusu',     'isaac.owusu@example.com',      '+15875550111', true),
    ('c1000000-0000-0000-0000-000000000012', 'Deborah',  'Chukwu',    'deborah.chukwu@example.com',   '+15875550112', true);


-- ============================================================
-- APP ROLES
-- Samuel and Grace are admins; Daniel, Esther, Joshua, Mary are department heads
-- ============================================================
insert into public.worker_app_roles (worker_id, role) values
    ('c1000000-0000-0000-0000-000000000001', 'admin'),
    ('c1000000-0000-0000-0000-000000000002', 'admin'),
    ('c1000000-0000-0000-0000-000000000003', 'hod'),
    ('c1000000-0000-0000-0000-000000000004', 'hod'),
    ('c1000000-0000-0000-0000-000000000005', 'hod'),
    ('c1000000-0000-0000-0000-000000000006', 'hod'),
    ('c1000000-0000-0000-0000-000000000007', 'worker'),
    ('c1000000-0000-0000-0000-000000000008', 'worker'),
    ('c1000000-0000-0000-0000-000000000009', 'worker'),
    ('c1000000-0000-0000-0000-000000000010', 'worker'),
    ('c1000000-0000-0000-0000-000000000011', 'worker'),
    ('c1000000-0000-0000-0000-000000000012', 'worker');


-- ============================================================
-- ASSIGN DEPARTMENT HEADS
-- ============================================================
update public.departments set hod_id = 'c1000000-0000-0000-0000-000000000003'
    where id = 'a1000000-0000-0000-0000-000000000001'; -- Daniel heads Ushers

update public.departments set hod_id = 'c1000000-0000-0000-0000-000000000004'
    where id = 'a1000000-0000-0000-0000-000000000002'; -- Esther heads Choir

update public.departments set hod_id = 'c1000000-0000-0000-0000-000000000005'
    where id = 'a1000000-0000-0000-0000-000000000003'; -- Joshua heads Children's Ministry

update public.departments set hod_id = 'c1000000-0000-0000-0000-000000000006'
    where id = 'a1000000-0000-0000-0000-000000000004'; -- Mary heads Technical


-- ============================================================
-- WORKER DEPARTMENTS (membership + role per department)
-- ============================================================
insert into public.worker_departments (worker_id, department_id, department_role_id) values
    -- Ushers
    ('c1000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000001'), -- Daniel → Head Usher
    ('c1000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000002'), -- Emmanuel → Floor Usher
    ('c1000000-0000-0000-0000-000000000009', 'a1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000003'), -- Peter → Door Usher
    ('c1000000-0000-0000-0000-000000000011', 'a1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000002'), -- Isaac → Floor Usher
    -- Choir
    ('c1000000-0000-0000-0000-000000000004', 'a1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000004'), -- Esther → Choir Director
    ('c1000000-0000-0000-0000-000000000008', 'a1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000006'), -- Ruth → Soprano
    ('c1000000-0000-0000-0000-000000000010', 'a1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000005'), -- Abigail → Alto
    ('c1000000-0000-0000-0000-000000000012', 'a1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000005'), -- Deborah → Alto
    -- Children's Ministry
    ('c1000000-0000-0000-0000-000000000005', 'a1000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000008'), -- Joshua → Ministry Lead
    ('c1000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000009'), -- Grace → Teacher
    ('c1000000-0000-0000-0000-000000000012', 'a1000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000010'), -- Deborah → Assistant (multi-dept)
    -- Technical
    ('c1000000-0000-0000-0000-000000000006', 'a1000000-0000-0000-0000-000000000004', 'b1000000-0000-0000-0000-000000000011'), -- Mary → AV Lead
    ('c1000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000004', 'b1000000-0000-0000-0000-000000000012'), -- Emmanuel → Sound Engineer (multi-dept)
    ('c1000000-0000-0000-0000-000000000011', 'a1000000-0000-0000-0000-000000000004', 'b1000000-0000-0000-0000-000000000013'), -- Isaac → Projectionist (multi-dept)
    -- Prayer Team
    ('c1000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000014'), -- Samuel → Prayer Lead
    ('c1000000-0000-0000-0000-000000000009', 'a1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000015'), -- Peter → Intercessor (multi-dept)
    ('c1000000-0000-0000-0000-000000000010', 'a1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000015'); -- Abigail → Intercessor (multi-dept)


-- ============================================================
-- AVAILABILITY
-- Recurring Sunday availability for all workers
-- Plus some specific date overrides (unavailable)
-- ============================================================
insert into public.availability (worker_id, availability_type, day_of_week, is_available) values
    -- All workers available Sundays by default (day_of_week = 0)
    ('c1000000-0000-0000-0000-000000000001', 'recurring', 0, true),
    ('c1000000-0000-0000-0000-000000000002', 'recurring', 0, true),
    ('c1000000-0000-0000-0000-000000000003', 'recurring', 0, true),
    ('c1000000-0000-0000-0000-000000000004', 'recurring', 0, true),
    ('c1000000-0000-0000-0000-000000000005', 'recurring', 0, true),
    ('c1000000-0000-0000-0000-000000000006', 'recurring', 0, true),
    ('c1000000-0000-0000-0000-000000000007', 'recurring', 0, true),
    ('c1000000-0000-0000-0000-000000000008', 'recurring', 0, true),
    ('c1000000-0000-0000-0000-000000000009', 'recurring', 0, true),
    ('c1000000-0000-0000-0000-000000000010', 'recurring', 0, true),
    ('c1000000-0000-0000-0000-000000000011', 'recurring', 0, true),
    ('c1000000-0000-0000-0000-000000000012', 'recurring', 0, true),
    -- Some workers also available Wednesdays (day_of_week = 3)
    ('c1000000-0000-0000-0000-000000000001', 'recurring', 3, true),
    ('c1000000-0000-0000-0000-000000000003', 'recurring', 3, true),
    ('c1000000-0000-0000-0000-000000000005', 'recurring', 3, true),
    ('c1000000-0000-0000-0000-000000000007', 'recurring', 3, true);

insert into public.availability (worker_id, availability_type, specific_date, is_available, notes) values
    -- Specific date overrides — workers marking themselves unavailable
    ('c1000000-0000-0000-0000-000000000007', 'specific_date', '2026-03-08', false, 'Travelling'),
    ('c1000000-0000-0000-0000-000000000010', 'specific_date', '2026-03-15', false, 'Family event'),
    ('c1000000-0000-0000-0000-000000000003', 'specific_date', '2026-03-22', false, 'Out of town');


-- ============================================================
-- SCHEDULES (upcoming Sunday services)
-- ============================================================
insert into public.schedules (id, department_id, title, scheduled_date, start_time, end_time, created_by) values
    ('d1000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'Sunday Morning Service — Ushers',           '2026-03-08', '08:30', '13:00', 'c1000000-0000-0000-0000-000000000003'),
    ('d1000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000002', 'Sunday Morning Service — Choir',            '2026-03-08', '08:00', '13:00', 'c1000000-0000-0000-0000-000000000004'),
    ('d1000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000003', 'Sunday Morning Service — Children',         '2026-03-08', '09:00', '12:00', 'c1000000-0000-0000-0000-000000000005'),
    ('d1000000-0000-0000-0000-000000000004', 'a1000000-0000-0000-0000-000000000004', 'Sunday Morning Service — Technical',        '2026-03-08', '07:30', '13:30', 'c1000000-0000-0000-0000-000000000006'),
    ('d1000000-0000-0000-0000-000000000005', 'a1000000-0000-0000-0000-000000000001', 'Sunday Morning Service — Ushers',           '2026-03-15', '08:30', '13:00', 'c1000000-0000-0000-0000-000000000003'),
    ('d1000000-0000-0000-0000-000000000006', 'a1000000-0000-0000-0000-000000000002', 'Sunday Morning Service — Choir',            '2026-03-15', '08:00', '13:00', 'c1000000-0000-0000-0000-000000000004'),
    ('d1000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000005', 'Wednesday Prayer Meeting',                  '2026-03-11', '18:00', '20:00', 'c1000000-0000-0000-0000-000000000001');


-- ============================================================
-- SCHEDULE ASSIGNMENTS
-- ============================================================
insert into public.schedule_assignments (schedule_id, worker_id, department_role_id) values
    -- March 8 — Ushers (Emmanuel is unavailable this day but assigned to test conflict detection)
    ('d1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000001'),  -- Daniel
    ('d1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000009', 'b1000000-0000-0000-0000-000000000003'),  -- Peter
    ('d1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000011', 'b1000000-0000-0000-0000-000000000002'),    -- Isaac
    ('d1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000007', 'b1000000-0000-0000-0000-000000000002'),    -- Emmanuel (unavailable — for testing)
    -- March 8 — Choir
    ('d1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000004', 'b1000000-0000-0000-0000-000000000004'),  -- Esther
    ('d1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000008', 'b1000000-0000-0000-0000-000000000006'),  -- Ruth
    ('d1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000010', 'b1000000-0000-0000-0000-000000000005'),    -- Abigail
    ('d1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000012', 'b1000000-0000-0000-0000-000000000005'),    -- Deborah
    -- March 8 — Children's Ministry
    ('d1000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000008'),  -- Joshua
    ('d1000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000009'),  -- Grace
    -- March 8 — AV
    ('d1000000-0000-0000-0000-000000000004', 'c1000000-0000-0000-0000-000000000006', 'b1000000-0000-0000-0000-000000000011'),  -- Mary
    ('d1000000-0000-0000-0000-000000000004', 'c1000000-0000-0000-0000-000000000011', 'b1000000-0000-0000-0000-000000000013'),    -- Isaac
    -- March 15 — Ushers
    ('d1000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000001'),    -- Daniel (unavailable Mar 22, not 15)
    ('d1000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000009', 'b1000000-0000-0000-0000-000000000003'),    -- Peter
    -- March 15 — Choir (Abigail unavailable this day)
    ('d1000000-0000-0000-0000-000000000006', 'c1000000-0000-0000-0000-000000000004', 'b1000000-0000-0000-0000-000000000004'),    -- Esther
    ('d1000000-0000-0000-0000-000000000006', 'c1000000-0000-0000-0000-000000000008', 'b1000000-0000-0000-0000-000000000006'),    -- Ruth
    -- Wednesday Prayer Meeting
    ('d1000000-0000-0000-0000-000000000007', 'c1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000014'),  -- Samuel
    ('d1000000-0000-0000-0000-000000000007', 'c1000000-0000-0000-0000-000000000009', 'b1000000-0000-0000-0000-000000000015');    -- Peter
