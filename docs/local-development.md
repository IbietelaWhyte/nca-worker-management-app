# Running the app locally

A fresh clone needs no credentials of its own. Local configuration is committed, because the
local Supabase keys are the published demo ones — identical on every machine and worthless
off it.

```sh
just install          # backend deps
just install-frontend # frontend deps
just dev              # starts the local database, then the API on :8000
just dev-frontend     # the SPA on :5173, in another terminal
```

Sign in with:

| | |
|---|---|
| Email | `test_user@test.com` |
| Password | `TestUserPassword123!` |
| Role | admin |

## Which database am I talking to?

`APP_ENV` decides, and it is the only setting that cannot live in a `.env` file — it chooses
which file to read.

| `APP_ENV` | Backend reads | Frontend reads |
|---|---|---|
| unset, `development`, anything else | `backend/.env.development` (committed) | `frontend/.env.development` (committed) |
| `production` | `backend/.env.production` (gitignored) | `frontend/.env.production` (gitignored) |

The frontend half needs no configuration at all: `npm run dev` is Vite's `development` mode
and `npm run build` is `production`, so the right file is picked without a flag.

**Both halves must agree.** The SPA signs in against its own `VITE_SUPABASE_URL` and the API
verifies the resulting token against that project's JWKS, so a local API paired with a hosted
frontend rejects every request with a 401.

Real environment variables still beat both files, which is how Railway and Vercel configure
their deployments — neither needs a `.env` file on the server.

### Running locally against production

Copy `.envrc.template` to `.envrc`, set `APP_ENV="production"`, and `direnv allow`. Then fill
in `backend/.env.production` from `backend/.env.production.example`. Do it deliberately: a
local API in production mode sends real SMS to real volunteers.

## The seeded data

`supabase db reset` applies every migration and then runs `supabase/seed.sql`.

- `20260303184000_seed_data.sql` (a migration) creates five departments, fifteen department
  roles, twelve workers with their app roles, and a month of rotas. None of those twelve can
  log in — they have no `auth.users` row, which is what `seed.sql` adds for the test user.
- `supabase/seed.sql` (local only) creates the admin above. It never runs against a hosted
  project: `supabase db push` does not execute seeds.

To start over: `just db-reset`.

### Writing a seed row for `auth.users` by hand

Worth knowing if you ever add a second account. Beyond the obvious columns, four have no
default and GoTrue scans them into plain Go strings, so leaving them NULL makes every sign-in
fail with `Database error querying schema` — an error that names neither the column nor the
row:

```sql
confirmation_token = '', recovery_token = '', email_change = '', email_change_token_new = ''
```

Three other things that will each cost an hour:

- `auth.identities` needs its own row, or the password grant finds nothing to authenticate.
- `confirmed_at` is a generated column; inserting into it is an error.
- `raw_app_meta_data.role` is the *only* thing the backend reads for authorization. Without
  it the account signs in successfully and can do nothing.

## Checking a token by hand

```sh
curl -X POST "http://127.0.0.1:54321/auth/v1/token?grant_type=password" \
  -H "apikey: $(grep '^SUPABASE_ANON_KEY=' backend/.env.development | cut -d= -f2-)" \
  -H "Content-Type: application/json" \
  -d '{"email": "test_user@test.com", "password": "TestUserPassword123!"}'
```

The `access_token` it returns goes straight into `Authorization: Bearer …` against
`http://localhost:8000/api/v1/...`.

## Other local URLs

| | |
|---|---|
| Supabase Studio | http://127.0.0.1:54323 |
| Inbucket (all outgoing mail) | http://127.0.0.1:54324 |
| Postgres | `postgresql://postgres:postgres@127.0.0.1:54322/postgres` |

`just db-env` prints the whole set.
