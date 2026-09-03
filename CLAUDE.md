# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

NCA Worker Management App — a church worker scheduler. A monorepo with three parts:

- `backend/` — FastAPI (Python 3.13, managed by `uv`). The "Church Worker Scheduler API".
- `frontend/` — React 18 + Vite SPA (plain JavaScript/JSX, not TypeScript).
- `supabase/` — Postgres schema as SQL migrations; auth is Supabase Auth.

The top-level `justfile` orchestrates both apps. The root `package.json` only carries the Supabase CLI and a couple of stray deps — it is not the app entrypoint. Root `README.md` is the **Supabase CLI's** README, checked in by accident at the first commit; it documents nothing about this project — ignore it.

## Commands

All common workflows go through `just` (run from repo root):

```sh
just install          # backend deps via `uv sync --all-extras`
just install-frontend # frontend deps via npm install
just dev              # backend dev server (uvicorn --reload on :8000)
just dev-frontend     # frontend dev server (vite on :5173)
just test             # backend pytest
just test-cov         # pytest with coverage
just lint             # ruff check --fix (backend) + eslint (frontend)
just format           # ruff format (backend) + prettier (frontend)
just typecheck        # mypy app (backend, strict mode)
just check            # lint + format + typecheck + test (run before pushing)
just build-frontend   # vite build
```

Run a single backend test:

```sh
cd backend && uv run pytest tests/unit/services/test_schedule_service.py
cd backend && uv run pytest tests/unit/services/test_schedule_service.py::test_name
```

Backend config comes from env vars (`Settings` in `core/config.py`, `env_file=".env"`). There is no committed `backend/.env`; the repo uses **direnv** — `.envrc` (gitignored) exports everything. If the backend fails at import with a pydantic validation error, the environment isn't loaded.

`FRONTEND_URL` is the one setting a deployment must not forget: it is the base of every link sent by SMS, and its default is `http://localhost:5173`, so leaving it unset ships dead links to real phones with no error anywhere. `Settings._check_frontend_url` refuses to start on a localhost URL when `APP_ENV=production` — which only helps if the deployment sets `APP_ENV` too.

`just install-hooks` installs a pre-commit hook that runs ruff check/format + mypy (backend) and prettier (frontend) (`scripts/install-hooks.sh`, copied from `.git-hooks/`). CI (`.github/workflows/ci.yml`) additionally enforces `ruff format --check` and runs the frontend build — formatting must be committed. Backend style: ruff `line-length = 120`, lint rules `E, F, I`; mypy `strict = true`.

`CLAUDE.md` is committed — keep it in step with the code when a change makes it stale.

## Backend architecture

Strict three-layer pattern, one package per domain. Domains: `workers`, `departments`, `department_roles`, `schedules`, `availabilities`, `subteams`, `account`, `authentication`, `confirmation_tokens`, plus the `reminders`/`sms` services.

- **router/** — FastAPI endpoints. Validate input, delegate authorization to the service, delegate work to a service. All routers mounted under `/api/v1`.
- **service/** — Business logic **and authorization**. Services depend only on repositories and other services (constructor-injected).
- **repository/** — Data access via the Supabase client. All extend `BaseRepository` (`repository/repository.py`), a generic that provides CRUD + Pydantic-model validation; subclasses add domain queries.
- **schemas/** — Pydantic models per domain. Cross-cutting enums (`UserRole`, `WorkerStatus`, `AssignmentStatus`, `DayOfWeek`, `AvailabilityType`, `TokenPayload`, `PaginatedResponse`) live in `schemas/models.py`.

**Dependency injection** is centralized in `core/dependencies.py`. Every repository and service has a `get_*` factory wired with `Depends(...)`. Routers import these factories plus the auth dependencies (`CurrentUser`, `AdminUser`, `HODUser`) re-exported from the same file — that is the single import point for wiring.

`core/` also holds: `config.py` (pydantic-settings `Settings`), `supabase.py` (singleton service-role client + httpx pool tuning), `authentication.py` (JWKS fetch/cache + JWT verification + role guards), `exceptions.py` (domain errors), `concurrency.py` (thread-pool cap), `phone.py` (E.164 normalization), `redaction.py` (PII masking), `logging.py` (structlog), `middleware.py` (request logging).

`app/main.py` builds the app, includes routers, registers the exception handlers, exposes `/health` and `/health/db`, and uses a `lifespan` context to configure the thread pool, start/stop the `ReminderService`, and warm the JWKS cache.

### Conventions that are easy to violate

- **Errors**: services raise the domain errors in `core/exceptions.py` (`NotFoundError` 404, `ConflictError` 409, `BadRequestError` 400, `PermissionDeniedError` 403, `GoneError` 410, base `AppError` 500). The `AppError` handler in `main.py` maps them to responses. Do **not** raise `HTTPException` from services, and do not let routers guess a status from an exception message. A catch-all handler returns a generic 500 so internals never leak.
- **Query constants**: each repository package has a `queries.py` holding `TABLE`, `SELECT_*` strings, and `Columns` / `JunctionColumns` classes. Repositories reference those constants — don't inline table or column string literals.
- **PostgREST filter injection**: any user-supplied value embedded in an `or()`/filter expression must go through `quote_postgrest_value` (`repository/filters.py`). Commas, dots and parens are filter syntax in PostgREST.
- **An `on_conflict` target must be backed by a NON-PARTIAL unique index.** PostgREST's `on_conflict` parameter can only carry a column list, and Postgres refuses a partial unique index as an `ON CONFLICT` arbiter unless the statement repeats the index predicate — which PostgREST has no way to send. A partial index behind an upsert therefore fails every call with `42P10: there is no unique or exclusion constraint matching the ON CONFLICT specification`. This is what broke every specific-date availability save; see `20260902120000_availability_specific_date_index.sql`. (`uq_schedules_dept_date_no_subteam` is partial for a different reason and is not an upsert target — don't copy it into one.)
- **A write does not return its embeds.** PostgREST returns base-table columns only from an `UPDATE`/`INSERT`, and `.select()` is **not** chainable onto `.update()` in supabase-py — `update()` hands back a `SyncFilterRequestBuilder` with no `select`. So a repository write whose caller renders nested data must re-read: `update_assignment_status` / `update_assignment_role` update and then return `get_assignment_by_id(...)`, which selects `SELECT_ASSIGNMENT_WITH_RELATIONS`. The embeds on `AssignmentResponse` are all `X | None = None`, so a bare row validates silently and the frontend just renders "Unknown worker" — Pydantic cannot catch this for you.
- **A nullable column needs an optional field.** A Pydantic field typed `X` against a column that is `NULL`-able raises `ValidationError` the moment a NULL row is read — and because these models are validated deep inside repository reads, that surfaces as an unrelated 500 far from the cause (`Schedule.created_by` took down schedule generation from inside the round-robin sort). Check the FK too: `ON DELETE SET NULL` means NULL is a designed state, not an anomaly, so the model must allow it rather than the column being tightened.
- **Logging PII**: emails and phone numbers get masked with `mask_email` / `mask_phone` (`core/redaction.py`) before reaching a log call.
- **Handlers are sync (`def`, not `async def`)** on purpose, so FastAPI runs them in a worker thread. `configure_thread_pool()` caps that pool at `settings.request_thread_pool_size`, and `Settings` validates `request_thread_pool_size <= db_max_connections` — otherwise surplus handlers block on the shared Supabase httpx pool and fail with pool timeouts. Keep the invariant if you touch either knob. Operational knobs like these belong in `Settings`, not as hardcoded constants.
  The one deliberate exception is the CSV import endpoint, which must be `async def` to `await file.read()` on the `UploadFile`; it hands the bytes straight to the sync service.

## Authentication & roles

Auth is delegated to **Supabase**. The frontend signs in with `@supabase/supabase-js` and attaches the access token as a `Bearer` header (see `frontend/src/api/client.js` interceptor). The backend verifies the Supabase JWT against the cached JWKS (`core/authentication.py`, with a one-shot refresh on an unknown `kid`) — it never issues its own tokens. The backend's own Supabase client uses the **service role key**, so it bypasses RLS; authorization is therefore the app's job.

Four roles (`UserRole` in `schemas/models.py`, declared in descending privilege): `admin`, `hod`, `assistant_hod`, `worker`.

**Two different things are called "role" — keep them apart:**

- `worker_app_roles` (+ `department_assistant_hods`, `departments.hod_id`) — the *permission* level. This is `UserRole`.
- `department_roles` — a *job within a department* ("Head Usher"), assigned per `worker_departments` row and optionally per schedule assignment. Its own domain package and `/api/v1/roles` router.

**Role sync is load-bearing.** `worker_app_roles` is the source of truth, but authorization reads only the single role baked into the JWT's `app_metadata.role`. `WorkerService._sync_role_to_auth` mirrors `highest_role(roles)` into Supabase auth on every role change; without it a role change never takes effect for a logged-in user. It no-ops for workers with no `auth_user_id` (a worker record can exist without a login account — admins grant one later via `AuthenticationService.create_account_for_worker`).

**Where authorization lives:** simple gates use the `AdminUser` / `HODUser` dependencies. Anything scope-dependent goes through `WorkerService.authorize_*` (`authorize_view_worker`, `authorize_update_worker`, `authorize_manage_worker`, `authorize_create_assignment`) — routers call these, they raise `PermissionDeniedError`. Postgres **RLS policies** in the migrations encode the same rules for direct DB access; keep both in sync when changing access rules.

HOD/assistant-HOD scoping is non-trivial: a worker's managed departments come from two sources — `departments.hod_id` (for HODs) and the `department_assistant_hods` table (for assistant HODs). `WorkerService.can_manage_worker` / `get_managed_department_ids` union both. See `docs/assistant-hod-department-association.md` for the design rationale (why a separate table rather than a nullable column).

## Scheduling (core domain logic)

`ScheduleService.generate_schedule` (`service/schedules/service.py`) is the heart of the app. It supports three scopes (`ScopeType`): `SUBTEAM`, `DEPARTMENT_ONLY` (workers in the department but in no subteam), and `DEPARTMENT_ALL`. The pipeline: resolve workers-needed by scope → gather eligible workers → filter by availability → drop workers already scheduled that date (no double-booking) → assign via round-robin by least-recently-assigned.

Workers-needed resolves as `subteams.workers_per_slot` falling back to `departments.workers_per_slot` when null.

Note the day-of-week convention mismatch: the DB stores `0 = Sunday` (and `DayOfWeek.to_number()` follows it), Python's `weekday()` uses `0 = Monday`. Conversions are explicit in the service — preserve them.

### Monthly generation (two-phase)

Generating a whole month is a separate path from `generate_schedule`, and deliberately not a new entity — a "month" is just N ordinary `schedules` rows that fall in the same month. It is two-phase, driven by two endpoints (`POST /schedules/generate-month/preview`, then `POST /schedules/generate-month`):

1. `preview_monthly_schedule` plans the month and **writes nothing**, returning a per-date `DatePlan` (with `DatePlanStatus`, selected workers and alternates) for the HOD to review.
2. `commit_monthly_schedule` persists only the dates the HOD kept (`DateSelection`), and **rolls back every schedule it created** if assignment insertion fails — a partial commit must not leave a month of empty rotas.

`service/schedules/planner.py` holds the planning itself and is **pure — no I/O**. `ScheduleService._build_plan_context` preloads everything into a `PlanContext` in a fixed number of queries (a per-worker history fetch × a month of dates would be pathological), then `plan_month` runs in memory. Two rules shape it, and both are easy to break:

- **Dates are planned together**, ascending, carrying each pick into the next date's ordering. Sorting each date from the same starting state would hand the same few workers every week.
- **A date is filled group by group** (`ScopeGroup` / `GroupContext`). A `DEPARTMENT_ALL` schedule staffs each subteam to *its own* `workers_per_slot`, so each group plans against its own roster and quota; subteam-scoped and department-only are the one-group case.

One schedule per (department, date, subteam) was previously enforced only by the service's pre-insert check. `20260827090000_schedule_date_uniqueness.sql` adds it in Postgres as **two partial unique indexes** — a plain one would not stop two department-level rows (`subteam_id IS NULL`) on the same date, since Postgres treats NULLs as distinct.

The planner is tested directly in `tests/unit/services/test_schedule_planner.py` — no repository mocks needed, which is the point of keeping it pure.

## Bulk CSV worker import

`WorkerService.import_workers` backs `POST /api/v1/departments/{department_id}/workers/import` (on the **departments** router, not workers — and declared before `/{department_id}/workers/{worker_id}` so `import` is not parsed as a UUID). Same two-phase shape as monthly generation: the frontend `CsvImportDialog` calls it with `dry_run=true` for a per-row preview, then again to commit.

- **All-or-nothing.** The file is fully parsed and validated before anything is written; one bad row rejects the whole import.
- **Duplicates are not errors.** Re-uploading a roster is normal, so existing workers are reported separately (`duplicate` / `duplicate_inactive`). They still block by default; `skip_duplicates=true` imports the remainder — an explicit choice after seeing the preview, never a silent skip.
- Whole-file problems (too large, not UTF-8, empty, missing a required column, over the row limit) raise `BadRequestError`; per-row problems become row results. Limits are `settings.max_import_file_bytes` / `max_import_rows`.
- Validation messages are rewritten for volunteers editing a spreadsheet (`_VALIDATION_MESSAGES`), not Pydantic's developer-facing text. Keep that mapping in step with the validators on `WorkerImportRow`.
- Phone numbers go through `core/phone.py` `normalize_phone` into E.164 — Twilio silently fails on anything else, so every phone entering the system should pass through it.
- The downloadable template is `frontend/public/worker-import-sample.csv`. `tests/unit/test_import_template.py` parses that actual file as a drift guard, so edit template and parser together.

## Reminders & SMS

`ReminderService` (`service/reminders/`) runs an APScheduler `BackgroundScheduler` cron job daily at **08:00** to SMS workers about upcoming assignments (`schedules.reminder_days_before` controls the lead time; `trigger_manually` / `trigger_for_schedule` force a run). SMS goes through `SMSService` (`service/sms/`, Twilio). Each reminder embeds a one-time confirmation link backed by `confirmation_tokens`; workers confirm/decline via the unauthenticated `/api/v1/confirm/{token}` endpoints, surfaced by the frontend `/confirm/:token` page.

The reminder job runs on its own thread outside the request thread pool — that gap between `request_thread_pool_size` and `db_max_connections` is what reserves connections for it.

**Keep every message body inside GSM-7.** One character outside that alphabet — an em dash, a curly quote, an emoji — switches the whole SMS to UCS-2, which cuts a segment from 160 characters to 70 and so silently doubles or triples the cost of a long roster. Nothing errors; the message just arrives billed as three segments instead of one. `SMSService._describe_duties` uses a plain `-` between groups for exactly this reason, and `test_sms_service.py` asserts the rendered bodies character-by-character against the GSM-7 set. Assert the whole body in a test when you add a message — the multi-date notice once shipped with no separator at all (`dates:Sun 02 Aug...`) because nothing checked the string.

The notice and the confirmation page get their department name by **different routes, and have to**: the notice path goes through the `get_assignments_due_for_notice` RPC, which returns `row_to_json(s)` and so cannot carry an embed, hence `ReminderService._department_name` and its per-run cache; the confirmation page path is a plain PostgREST select and gets `departments(*)` embedded for free. Don't "unify" one into the other without changing the RPC's return signature.

## Frontend architecture

- Routing in `src/App.jsx`; every page is `lazy()`-loaded so each ships as its own chunk. Authenticated routes are wrapped in `ProtectedLayout` (= `ProtectedRoute` + `AppLayout`). Public routes: `/login`, `/reset-password`, and `/confirm/:token` (reached from an SMS link, no session).
- Auth state via `src/context/AuthContext.jsx` (`useAuth()` hook) — exposes `role`, `isAdmin`, `isDepartmentHead` (true for `hod`, `assistant_hod`, **and** `admin`), `signIn`, `signOut`, sourced from the Supabase session's `app_metadata.role`. It carries **no worker id and no department ids** — `auth_user_id` is `exclude=True` on the worker schema, so anything keyed to the signed-in person goes through `GET /account/me` first (`getMyProfile()`), as `useMyDuties` does.
- **`GET /departments` is scoped for heads of department but NOT for plain workers.** The handler branches on `hod`/`assistant_hod` and returns their departments; every other role, `worker` included, falls through to `get_all_departments`. So "the departments I can see" is only a safe basis for a view when gated on `isDepartmentHead` — `DashboardPage` does exactly this, and a worker gets their own duties instead. Don't build a second view on that endpoint without the same gate.
- The dashboard (`src/pages/DashboardPage.jsx` + `src/components/dashboard/`) has **three modes from one layout**: admin and HOD share the department board, differing only in how many departments the API returns, and a worker gets `MyDuties`. Its aggregation lives in `src/lib/dashboard.js`, kept pure and React-free like `lib/rota.js` — `summarizeAssignments` there is the single copy of the confirmed/total helper that the schedules table and month grid also use. There is no whole-church schedule endpoint, so `useDashboard` fans out one `getSchedulesByDepartment` per department; fine at a handful, worth a real endpoint past ~15.
- `src/api/` — one module per domain, all using the shared `apiClient` (`src/api/client.js`), which attaches the bearer token and logs requests/responses **only under `import.meta.env.DEV`**, with sensitive fields stripped by `redact()`. Keep new logging behind that guard.
- `src/hooks/` — one `use<Domain>` hook per domain wrapping the api modules; they own `{ data, loading, error, refetch, ...mutations }` and patch local state after a mutation resolves rather than refetching. Prefer a hook for list/CRUD state; a few pages (`AccountPage`, `ConfirmPage`, `ScheduleDetailPage`, `DepartmentDetailPage`) still call `src/api/` directly for one-off calls.
- UI built with shadcn-style components in `src/components/ui/` + Tailwind, with per-domain component folders. Path alias `@/` → `src/` (see `jsconfig.json` / `vite.config.js`).
- **Theming.** Colour and type follow the church website (newcovenantassembly.ca), whose Elementor kit is the source of the values: purple `#662E91`, red `#C1272D`, gold `#ECCE68`, body grey `#666B68`, heading ink `#0F0F0F`, all in **Epilogue** (self-hosted via `@fontsource-variable/epilogue`). Everything is defined once as HSL triples in the `:root` block of `src/index.css` and exposed through the `@theme` block at the top of the same file — **use the tokens, never a raw palette class** (`bg-green-600`, `text-gray-500`); a `grep -rE "(bg|text|border)-(gray|green|red|amber)-[0-9]" frontend/src/` should stay empty. Three points that are easy to get wrong:
    - `--accent` is shadcn's *hover surface*, not the brand accent. The gold lives in `--highlight` / `--warning`; putting it in `--accent` turns every hover in the app yellow. Gold takes dark ink only — white on it is 1.54:1.
    - Purple is `--primary` and red is `--destructive`, deliberately, so "Save" and "Delete" never look alike. `--success` / `--warning` exist for the semantic cases the public pages need.
    - `RotaExportDialog.jsx` keeps **fixed hex constants** because the JPEG is rasterised and shared outside the app; they mirror the tokens by hand, so change them together. The sidebar has its own `--sidebar-*` set because it sits on purple, where the ordinary foreground tokens don't apply.
- **Mobile.** The app is responsive from 375px up, and `md` (768px) is the line: below it the sidebar becomes a slide-out drawer (`ui/sheet.jsx`, held open by `AppLayout`), and the browse tables are replaced by card lists — `hidden md:block` on the `<Table>`, a `md:hidden` `<ul>` of cards beside it, both fed from the same array. Follow that pattern rather than inventing a shared abstraction; each table's cards need their own judgement about which fields survive. Page headers are `flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between`, and button clusters carry `flex-wrap`. **The rule to hold: no page may scroll horizontally at 375px** — inner scrollers (a table, the month grid) are fine and expected. `scripts/` has no checker for this; measure `document.documentElement.scrollWidth` against the viewport when touching layout. Two traps: any control under 16px triggers iOS zoom-on-focus, so form controls are `text-base sm:text-sm` (see `ui/input.jsx`); and `min-h-screen` is `100vh` even in v4, which sits under mobile browser chrome — the public pages use `min-h-dvh`.
- **Tailwind v4**, via `@tailwindcss/vite` — there is no `tailwind.config.js` and no `postcss.config.js`. The theme lives in the `@theme` block at the top of `src/index.css`; `content` is auto-detected, and `darkMode: 'class'` is now the `@custom-variant dark` line. The `ui/` primitives came from the shadcn radix-nova registry, which targets v4, so **write v4 syntax** (`size-(--cell-size)`, `data-open:`, `outline-hidden`, `ring-3`). Two things the migration had to pin down and that a future edit could undo: `@import 'tw-animate-css'` must **not** be given `layer(...)` — it defines `@utility` rules, which cannot be nested, and without it every overlay animation silently disappears; and `calendar.jsx`'s `[--cell-size:--spacing(11)]` is deliberately 44px rather than the registry's 7 (28px), which would put every calendar below the touch-target minimum.
- `VITE_API_BASE_URL` points at the backend.

## Database migrations

Schema lives only in `supabase/migrations/` (no ORM). Workflow:

```sh
supabase migration new $NAME    # create
supabase migration up           # apply locally
supabase db push                # push to remote
supabase db reset               # reset + reapply + seed
supabase migration repair --status reverted $MIGRATION_ID   # after a failed push
```

Core tables: `workers`, `worker_app_roles`, `departments`, `department_roles`, `worker_departments` (junction, carries `department_role_id` + `subteam_id`), `subteams`, `availability`, `schedules`, `schedule_assignments`, `department_assistant_hods`, `confirmation_tokens`. RLS helpers defined in SQL: `current_worker_id()`, `has_app_role()`, `is_hod(dept_id)`.

See `docs/database-migrations.md`. When adding tables/columns, also add RLS policies and update the corresponding repository (`queries.py` constants included) + Pydantic schema.

## Testing

`backend/tests/`:

- `unit/services/` — business logic with repositories mocked.
- `unit/test_*.py` — core primitives (`BaseRepository`, filter escaping, redaction, concurrency, JWT verification, phone normalization) and repository query behavior (`test_worker_repository_*.py`, `test_schedule_repository_upcoming.py`).
- `unit/services/test_schedule_planner.py` — the pure monthly planner, no mocks. `unit/test_import_template.py` reads the real `frontend/public/worker-import-sample.csv`, so it fails if template and parser drift apart.
- `integration/routers/` — endpoint behavior; also `test_health.py` and `test_exception_handlers.py`.

`pytest` runs in asyncio auto mode. `tests/conftest.py` provides role-scoped `TestClient` fixtures (`admin_client`, `hod_client`, `worker_client`) that work by overriding `app.dependency_overrides[verify_token]` — that is the way to test authorization, no real tokens involved.

There is no frontend test suite — CI validates the frontend via lint + build.
