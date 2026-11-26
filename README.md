# NCA Worker Management

Scheduling for the volunteers who serve at New Covenant Assembly. Heads of department build
fair monthly rotas, and the app texts each person their duties, reminds them beforehand, and asks
them which dates they can't make.

Live at **https://nca-worker-management-app.vercel.app** (sign-in is by invitation).

## What it does

- **Rotas.** Generate a single date or a whole month. A head previews it, keeps the dates they
  want, and saves it as a draft or publishes it. Picks rotate fairly, and big services
  ("special services") get their own rotation so the same few people don't serve every one.
  Rotas can be edited by hand afterwards.
- **Availability.** Workers mark only the dates they *can't* serve, from a link texted to them.
  It needs no account, so silence means "available". Heads can send these requests now or on a
  monthly schedule.
- **Text messages** (Twilio). A notice when someone is rostered, reminders at the lead times
  the head chooses, and a text when a duty is cancelled. Numbers that have opted out are not
  texted again.
- **Teams.** Departments, subteams, roles within a department (with minimum counts per rota),
  leave, and "Teacher of the Month"-style leads.
- **Attendance.** Whoever runs a service checks people in from a phone, and heads get a
  per-department report with a CSV export.
- **Accounts.** Admins invite heads by email and the person chooses their own password. Most
  volunteers never need a login.

## How it's built

| Part | Stack | Hosted on |
|---|---|---|
| `frontend/` | React 18 + Vite, Tailwind v4, shadcn/Radix components | Vercel |
| `backend/` | FastAPI on Python 3.13 (`uv`), APScheduler for the text sweeps | Railway |
| `supabase/` | Postgres schema as SQL migrations, Supabase Auth | Supabase |

The browser uses Supabase only to sign in. Everything else goes through the API, which checks
the Supabase token and enforces who may see and change what.

## Running it locally

You need [`just`](https://github.com/casey/just), [`uv`](https://docs.astral.sh/uv/),
Node 20+, and Docker (for the local Supabase stack). The Supabase CLI is installed by
`npm install` at the repo root and run through `npx`.

```sh
npm install            # the pinned Supabase CLI
just install           # backend dependencies
just install-frontend  # frontend dependencies
just dev               # starts local Supabase, then the API on :8000
just dev-frontend      # the app on http://localhost:5173 (in another terminal)
```

No credentials are needed. Local configuration is committed because the local Supabase keys are
the same on every machine. Sign in as `test_user@test.com` / `TestUserPassword123!` (an admin).
Emails the app would send, such as invites and password resets, land in Mailpit at
http://127.0.0.1:54324. No real texts go out: the local Twilio credentials are placeholders, so
sends fail and are only logged.

| Command | What it does |
|---|---|
| `just check` | Lint, format, type-check and test. Run it before pushing; CI runs the same checks. |
| `just test` | Backend tests (pytest) |
| `just db-reset` | Rebuild the local database from the migrations and seed data |
| `just install-hooks` | Install the pre-commit hook (ruff, mypy, prettier) |
| `just build-frontend` | Production build of the app |

There is no frontend test suite. CI checks the frontend with lint, a build, and an audit of
production dependencies.

## Documentation

- [`CLAUDE.md`](CLAUDE.md): the architecture and the design decisions behind it, including
  the conventions that are easy to break. Read this before changing anything significant.
- [`docs/local-development.md`](docs/local-development.md): local setup in detail, and how to
  point a local API at production.
- [`docs/database-migrations.md`](docs/database-migrations.md): creating and applying schema
  changes.
- [`docs/smtp-setup.md`](docs/smtp-setup.md): how auth email is sent and switched between
  providers.
- [`docs/church-onboarding.md`](docs/church-onboarding.md): what is left to move the app from a
  one-department pilot to church-wide.
- [`docs/assistant-hod-department-association.md`](docs/assistant-hod-department-association.md):
  why assistant heads are linked to departments the way they are.

## Licence

Copyright © 2026 Ibietela Whyte. All rights reserved. The code is public for reference only;
see [`LICENSE`](LICENSE).
