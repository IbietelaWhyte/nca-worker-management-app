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
