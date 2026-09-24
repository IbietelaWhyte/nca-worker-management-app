# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

NCA Worker Management App — a church worker scheduler. A monorepo with three parts:

- `backend/` — FastAPI (Python 3.13, managed by `uv`). The "Church Worker Scheduler API".
- `frontend/` — React 18 + Vite SPA (plain JavaScript/JSX, not TypeScript).
- `supabase/` — Postgres schema as SQL migrations; auth is Supabase Auth.

The top-level `justfile` orchestrates both apps. The root `package.json` only carries the Supabase CLI and a couple of stray deps — it is not the app entrypoint. Root `README.md` is the **Supabase CLI's** README, checked in by accident at the first commit; it documents nothing about this project — ignore it. `frontend/README.md` is likewise the stock Vite template.

## Commands

All common workflows go through `just` (run from repo root):

```sh
just install          # backend deps via `uv sync --all-extras`
just install-frontend # frontend deps via npm install
just db-start         # local Supabase stack (idempotent); db-stop, db-reset, db-env beside it
just dev              # backend dev server (uvicorn --reload on :8000); starts the local DB first
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

**`APP_ENV` picks the credentials file, and is the only setting that cannot live in one.** `Settings` (`core/config.py`) resolves `backend/.env.$APP_ENV` at import, where anything other than `production` means `development` — the same strict equality `is_production` uses. It comes from the shell, so `.envrc` (gitignored) holds that one line and nothing else; unset means development, so production has to be asked for. The path is resolved from the module's own location rather than the CWD: `env_file=".env"` only worked because the backend is always started from `backend/`, and pytest from the repo root silently read no file at all.

**Local credential files are committed, production ones are not.** `backend/.env.development` and `frontend/.env.development` hold Supabase's published demo keys — the same on every machine, worthless off it — so a fresh clone runs `just dev` with no setup and `just test` needs no direnv. `.gitignore` is deny-then-allow (`.env.*` then `!.env.development`), so a future `.env.staging` fails closed. Real environment variables still beat both files, which is how Railway and Vercel configure their deployments and why CI is unaffected.

**The frontend half needs no wiring at all.** `npm run dev` is Vite's `development` mode and `npm run build` is `production`, so `frontend/.env.$mode` is picked without a flag — which is why no justfile recipe sets an environment variable. **Both halves must agree**: the SPA signs in against its own `VITE_SUPABASE_URL` and the backend verifies that token against the same project's JWKS, so a mismatched pair 401s everything.

`supabase/seed.sql` gives a local stack the one thing the migrations cannot: an account to sign in as (`test_user@test.com` / `TestUserPassword123!`, admin). It runs on `db reset` and never on `db push`. A hand-written `auth.users` row has four traps, all documented in `docs/local-development.md` — the sharpest being that `confirmation_token`, `recovery_token`, `email_change` and `email_change_token_new` have no default and GoTrue scans them into plain Go strings, so a NULL fails every sign-in with `Database error querying schema`.

See `docs/local-development.md` for the whole setup.

`FRONTEND_URL` is the one setting a deployment must not forget: it is the base of every link sent by SMS, and its default is `http://localhost:5173`, so leaving it unset ships dead links to real phones with no error anywhere. `Settings._check_frontend_url` refuses to start on a localhost URL when `APP_ENV=production` — which only helps if the deployment sets `APP_ENV` too.

`just install-hooks` installs a pre-commit hook that runs ruff check/format + mypy (backend) and prettier (frontend) (`scripts/install-hooks.sh`, copied from `.git-hooks/`). CI (`.github/workflows/ci.yml`) additionally enforces `ruff format --check` and runs the frontend build — formatting must be committed. Backend style: ruff `line-length = 120`, lint rules `E, F, I`; mypy `strict = true`.

`CLAUDE.md` is committed — keep it in step with the code when a change makes it stale.

## Backend architecture

Strict three-layer pattern, one package per domain. Domains: `workers`, `worker_leave`, `departments`, `department_roles`, `schedules`, `availabilities`, `availability_prompts`, `subteams`, `account`, `authentication`, `confirmation_tokens`, `feedback`, plus the `reminders`/`sms` services. Not every domain has all four layers: `feedback`, `reminders` and `sms` have no repository; `availability_prompts` has no router (its endpoints hang off the departments router); and `confirmation_tokens` has no router at all — it is read by the availability router and the prompt service, never addressed directly.

- **router/** — FastAPI endpoints. Validate input, delegate authorization to the service, delegate work to a service. All routers mounted under `/api/v1`.
- **service/** — Business logic **and authorization**. Services depend only on repositories and other services (constructor-injected).
- **repository/** — Data access via the Supabase client. All extend `BaseRepository` (`repository/repository.py`), a generic that provides CRUD + Pydantic-model validation; subclasses add domain queries.
- **schemas/** — Pydantic models per domain. Cross-cutting enums (`UserRole`, `WorkerStatus`, `DayOfWeek`, `AvailabilityType`, `TokenPayload`, `PaginatedResponse`) live in `schemas/models.py`.

**Dependency injection** is centralized in `core/dependencies.py`. Every repository and service has a `get_*` factory wired with `Depends(...)`. Routers import these factories plus the auth dependencies (`CurrentUser`, `AdminUser`, `HODUser`) re-exported from the same file — that is the single import point for wiring.

`core/` also holds: `config.py` (pydantic-settings `Settings`), `supabase.py` (singleton service-role client + httpx pool tuning), `authentication.py` (JWKS fetch/cache + JWT verification + role guards), `exceptions.py` (domain errors), `concurrency.py` (thread-pool cap), `phone.py` (E.164 normalization), `redaction.py` (PII masking), `logging.py` (structlog), `middleware.py` (request logging).

`app/main.py` builds the app, includes routers, registers the exception handlers, exposes `/health` and `/health/db`, and uses a `lifespan` context to configure the thread pool, start/stop the `ReminderService`, and warm the JWKS cache.

### Conventions that are easy to violate

- **Errors**: services raise the domain errors in `core/exceptions.py` (`NotFoundError` 404, `ConflictError` 409, `BadRequestError` 400, `PermissionDeniedError` 403, `GoneError` 410, base `AppError` 500). The `AppError` handler in `main.py` maps them to responses. Do **not** raise `HTTPException` from services, and do not let routers guess a status from an exception message. A catch-all handler returns a generic 500 so internals never leak.
- **Query constants**: each repository package has a `queries.py` holding `TABLE`, `SELECT_*` strings, and `Columns` / `JunctionColumns` classes. Repositories reference those constants — don't inline table or column string literals.
- **PostgREST filter injection**: any user-supplied value embedded in an `or()`/filter expression must go through `quote_postgrest_value` (`repository/filters.py`). Commas, dots and parens are filter syntax in PostgREST.
- **An `on_conflict` target must be backed by a NON-PARTIAL unique index.** PostgREST's `on_conflict` parameter can only carry a column list, and Postgres refuses a partial unique index as an `ON CONFLICT` arbiter unless the statement repeats the index predicate — which PostgREST has no way to send. A partial index behind an upsert therefore fails every call with `42P10: there is no unique or exclusion constraint matching the ON CONFLICT specification`. This is what broke every specific-date availability save; see `20260902120000_availability_specific_date_index.sql`. (`uq_schedules_dept_date_no_subteam` is partial for a different reason and is not an upsert target — don't copy it into one.)
- **A write does not return its embeds.** PostgREST returns base-table columns only from an `UPDATE`/`INSERT`, and `.select()` is **not** chainable onto `.update()` in supabase-py — `update()` hands back a `SyncFilterRequestBuilder` with no `select`. So a repository write whose caller renders nested data must re-read: `update_assignment_status` / `update_assignment_role` update and then return `get_assignment_by_id(...)`, which selects `SELECT_ASSIGNMENT_WITH_RELATIONS`. The embeds on `AssignmentResponse` are all `X | None = None`, so a bare row validates silently and the frontend just renders "Unknown worker" — Pydantic cannot catch this for you.
- **A nullable column needs an optional field.** A Pydantic field typed `X` against a column that is `NULL`-able raises `ValidationError` the moment a NULL row is read — and because these models are validated deep inside repository reads, that surfaces as an unrelated 500 far from the cause (`Schedule.created_by` took down schedule generation from inside the fairness sort). Check the FK too: `ON DELETE SET NULL` means NULL is a designed state, not an anomaly, so the model must allow it rather than the column being tightened.
- **Route declaration order is load-bearing.** A literal segment must be declared before the `/{uuid}` route that would otherwise swallow it — `/departments/{id}/workers/import` before `/{department_id}/workers/{worker_id}`, `/leave/current` before `/leave/{leave_id}`, `/availability/config` and `/availability/link/{token}` before `/availability/{availability_id}`, and `DELETE /schedules/assignments/{id}` before `DELETE /schedules/{schedule_id}`. FastAPI matches in declaration order, so the symptom is a 422 complaining that "current" is not a valid UUID. `test_the_assignment_route_is_declared_before_the_schedule_route` guards the last of these.
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

**Password reset never touches the backend.** `LoginPage` calls `supabase.auth.resetPasswordForEmail` and `ResetPasswordPage` calls `supabase.auth.updateUser` directly — there is no API endpoint, and the backend sends no email of any kind. Delivery therefore depends on Supabase's SMTP settings rather than on anything in this repo: `RESEND_API_KEY` / `GMAIL_APP_PASSWORD` in `.envrc.template` are **not** read by `Settings` and exist only as a note to whoever fills in the Supabase dashboard. See `docs/smtp-setup.md`.

## Availability

**Availability is recorded negatively: a worker marks only the dates they CANNOT serve.** Everything absent is available. This is not a UI preference — it is what the rota already assumed (`_build_unavailability_map` treats a worker with no record as free), so a row saying "I can serve" is an opinion nothing acts on, and someone who ignores the text is scheduled either way. Asking for exceptions makes silence and "I am free" the same answer, which is what volunteers expect.

Consequences to preserve:

- The public page writes one thing. `PublicAvailabilityUpdate` carries **no `is_available` flag** and `AvailabilityService.mark_unavailable` hardcodes `is_available=False`. Don't reintroduce a "mark available" path on the token page.
- **A day has two states, not three** (unmarked ↔ cannot serve). The old cycle was unset → available → unavailable → unset; both editors and `SpecificDatesCalendar` are now toggles.
- **`is_available=True` specific-date rows still exist** from before the change and are filtered out of both reads (`get_public_availability`, `useAvailability`) rather than migrated away. They are harmless — `True` is the default anyway — but rendering one would read as a contradiction. The signed-in toggle replaces such a row by id when a date is re-marked, so it cannot appear twice.
- The column is still `is_available`, and the scheduler still reads it. Only the question the UI asks changed, not the storage.

**The cut-off.** `settings.availability_notice_days` closes a date `N` days before it falls; `AvailabilityService.editable_from()` is that boundary and `_ensure_editable` guards **every write naming a date** — `mark_unavailable`, `clear_specific_date`, `set_availability`, `update_availability` (both the old and the new date) and `delete_availability`. At the default of `0` only past dates are closed, which is the "you cannot enter September's availability in October" case. `clear_worker_availability` is deliberately exempt: it is a manager resetting a roster, and refusing it part-way would make a worker whose history straddles the cut-off permanently un-resettable.

The frontend greys closed days out rather than letting the tap fail, and needs the boundary from the server: the signed-in page reads `GET /availability/config`, and the public page gets the same `editable_from` inside its own response because it has no session to call a config endpoint with. Both are advisory — the service enforces it regardless.

**The SMS has to carry the inversion too.** Most people read the text and never tap through, so `SMSService.send_availability_prompt` says both which dates to mark and that no reply means they are free. Keep it inside GSM-7 (see the Reminders section) and keep it short: the wording has a character budget asserted in `test_sms_service.py`, because a 36-character token plus a real host already eats half a segment and a department is prompted every month.

### Prompts

Nothing asks a worker for their availability unless a head does. `AvailabilityPromptService` (`service/availability_prompts/`) texts a department's workers the public `/availability/{token}` link, either immediately or on a schedule. Its endpoints live on the **departments** router (`GET|POST /departments/{id}/availability-prompts`, `POST .../send`, `DELETE .../{prompt_id}`), driven by `AvailabilityPromptDialog`.

- **A scheduled send is a database row, not an in-process timer.** The `BackgroundScheduler` uses the default in-memory jobstore, so a job queued for next month would not survive a restart and would fire once per replica. A daily sweep (`send_due_prompts`) reads `availability_prompts` instead, with `last_sent_on` as the marker — the same nullable-column-as-marker idiom as `notice_sent_at`.
- Two modes: `once` (`send_on`) and `monthly` (`repeat_day`). `repeat_day` is capped at **28** so the day exists in February — landing slightly early beats silently skipping a month. The mode/field pairing is enforced twice, in `AvailabilityPromptCreate` and in Postgres check constraints; the Pydantic copy exists to give a person a message they can act on.
- A one-off is due on or **after** `send_on`, so a prompt whose day passed while the app was down still goes out. `last_sent_on` stops a second sweep the same day re-sending, and a sent one-off is deactivated. `mark_sent` runs even when some messages failed — a partial failure must not re-prompt the whole department.
- Recipients are the department's active workers minus anyone on leave **today**, and every outcome is counted (`sent`, `skipped_no_phone`, `skipped_on_leave`, `failed`): nothing else in the UI reveals a worker with no phone number.

### Leave

`worker_leave` records a stretch a worker is away (both ends **inclusive** — "away 10-20 Oct" includes the 20th). It does exactly two things: takes them out of schedule generation for the dates it covers, and stops the availability prompt texting them.

- **Not the same as `is_active`.** Deactivating strips someone from their departments and every roster; leave is temporary and leaves membership, roles and history intact, so they return without being re-added.
- **Not the same as availability, and deliberately its own table.** Availability is the worker's own answer about specific dates; leave is an absence a head records, and it is what suppresses the prompt — fold the two together and the prompt suppresses itself. A range also survives being extended, where expanding it into `availability` rows would bake today's service dates into storage and miss a schedule added later inside the window.
- **Set by heads and admins only** (`HODUser` + `authorize_manage_worker`). A worker marking individual dates off themselves is what `/availability` is for.
- **It never edits the rota.** `GET /leave/workers/{id}/clashes` reports duties already booked inside a proposed window so the head can reassign them; the dialog shows this *before* confirming. Duties stay put and the worker keeps their reminder, which is what prompts a decline if nobody gets to it.
- **Two different "on leave" questions, deliberately answered against different dates.** Generation asks "away on the date being scheduled" — batched through `get_for_workers` and `WorkerLeave.covers` inside `_build_unavailability_map`, on both the single-date and monthly paths; the prompt asks "away on the day the text goes out" (`get_active_on(today)`). A worker away for part of October still has other October dates worth asking about.
- Monthly generation folds leave into `_build_unavailability_map`, so **the planner stays pure and unchanged** — to it, someone away is just someone who cannot be picked. The cost: a plan's "3 unavailable" message does not separate leave from availability.
- Overlapping ranges are refused in the service, not by a constraint: excluding them in Postgres needs `btree_gist`, which would be the schema's first extension, and overlap is untidy rather than harmful since every read unions the rows.
- `PromptSendResult.skipped_on_leave` exists so a head who texts ten people and hears about eight is told why.

## Scheduling (core domain logic)

`ScheduleService.generate_schedule` (`service/schedules/service.py`) is the heart of the app. It supports three scopes (`ScopeType`): `SUBTEAM`, `DEPARTMENT_ONLY` (workers in the department but in no subteam), and `DEPARTMENT_ALL`.

**There is one selection algorithm, not two.** `generate_schedule` resolves its scope groups, then runs `plan_month` over a one-date list — the same pure planner the monthly path uses. It used to have its own sort, which had drifted: no tiebreaker (so two runs could pick different people), no month-count term (so three ad-hoc dates in a month went to overlapping people), and one history query per worker issued from *inside* the sort key. Any new selection rule belongs in `planner.py`, where it is written once and tested without mocks. The only thing the single-date path still does for itself is the pre-check that raises `ConflictError` naming the existing schedule's id.

**Staffing is a band, not a number.** `departments.min_workers_per_slot` / `max_workers_per_slot` are both NOT NULL; a subteam overrides **both or neither** (`chk_subteam_inherit_both`) — per-field inheritance would let a subteam's floor and the department's ceiling contradict each other across two rows where no constraint can see it. `_staffing_band()` resolves the pair and is the only place that does; it tests the override with `is None`, not `or`, because a minimum of 0 is now legitimate. The planner fills to the **maximum** and judges against the **minimum**: a group of 3 on a band of 2-4 is `PLANNED`, not `UNDERSTAFFED`.

The resolved band is frozen onto the schedule row (`schedules.min_workers` / `max_workers`, summed across groups), like `reminder_days_before`. Every screen that renders a schedule has only the schedule in scope, and a March rota must keep reading correctly after the department's numbers change in June. Both are nullable — rows predating the band have no honest answer, and `summarizeStaffing` falls back to the assignment count rather than claiming "0 needed".

### Editing a rota after generation

`add_assignment`, `replace_assignment_worker` and `remove_assignment` (`service/schedules/service.py`) repair a generated rota in place. There is no migration behind them: `unique (schedule_id, worker_id)` was already the right constraint, and `23505` maps to `ConflictError` through the existing `UNIQUE_VIOLATION` path.

- **An edit that makes the rota worse is allowed, with a warning.** Removing somebody below the minimum, or booking a worker who is on leave, marked off or already serving elsewhere that day, all go through and come back in `ScheduleEditResult.warnings`. A head recording what has actually happened must be able to, and refusing leaves the rota saying something untrue — the same line `worker_leave` takes with its clash report. Only three things refuse: an unknown record, somebody outside the scope, and an add that would pass the maximum.
- **The ceiling is the band frozen on the schedule row**, not the department's current one. It is the number every screen renders, so re-deriving it live would refuse an add at a figure nothing on screen names. A row predating the band (`max_workers IS NULL`) has no ceiling to enforce and the add goes through. A **swap is size-neutral and is not checked at all** — refusing one on a full rota would block the commonest edit precisely when the rota is correctly staffed.
- **`reassign_assignment` clears `notice_sent_at` and deletes the row's `assignment_reminder_sends`**, in that one repository method. The row now names somebody who has been told nothing; a stale `notice_sent_at` stops the notice sweep ever reaching them and a stale send marker cancels the reminder that would have. Neither errors — the first anyone hears is the empty chair. Deletion needs no such care: the marker rows go with the row on `ON DELETE CASCADE`.
- **Eligibility is resolved through `_resolve_scope_groups`**, the same call generation uses, so "who may be on this rota" has one definition and the group also says which subteam to stamp. A head picks a person, not a slot. `GET /schedules/{id}/assignable-workers` returns that list (`AssignableWorker`: worker + the subteam they would land in) so the picker offers exactly what an add would accept — working it out in JS would be a second copy of `_scope_of` plus the department-only rule, and a DEPARTMENT_ONLY rota excludes everybody who is in a subteam.
- `_scope_of(schedule)` reconstructs the scope, which the row does not record: a `subteam_id` means SUBTEAM, otherwise a non-null `subteam_id` on any assignment means DEPARTMENT_ALL, else DEPARTMENT_ONLY. The ambiguous case — a department-wide rota whose every pick happened to be un-subteamed — reads back as DEPARTMENT_ONLY, which narrows who may be added rather than widening it.
- **Both texts go out inline**, then `mark_notice_sent`. The sweep would find a fresh or reassigned row on its own, but only within `notice_interval_minutes`, and the head is standing in front of both people. A failed notice is left unmarked so the sweep retries; a failed **cancellation** has no such net (the row is gone) and is the one message in the system with no retry, so it becomes a warning telling the head to pass the word on themselves.

Note the day-of-week convention mismatch: the DB stores `0 = Sunday` (and `DayOfWeek.to_number()` follows it), Python's `weekday()` uses `0 = Monday`. Conversions are explicit in the service — preserve them.

### Monthly generation (two-phase)

Generating a whole month is a separate path from `generate_schedule`, and deliberately not a new entity — a "month" is just N ordinary `schedules` rows that fall in the same month. It is two-phase, driven by two endpoints (`POST /schedules/generate-month/preview`, then `POST /schedules/generate-month`):

1. `preview_monthly_schedule` plans the month and **writes nothing**, returning a per-date `DatePlan` (with `DatePlanStatus`, selected workers and alternates) for the HOD to review.
2. `commit_monthly_schedule` persists only the dates the HOD kept (`DateSelection`), and **rolls back every schedule it created** if assignment insertion fails — a partial commit must not leave a month of empty rotas.

`service/schedules/planner.py` holds the planning itself and is **pure — no I/O**. `ScheduleService._build_plan_context` preloads everything into a `PlanContext` in a fixed number of queries (a per-worker history fetch × a month of dates would be pathological), then `plan_month` runs in memory. Two rules shape it, and both are easy to break:

- **Dates are planned together**, ascending, carrying each pick into the next date's ordering. Sorting each date from the same starting state would hand the same few workers every week.
- **A date is filled group by group** (`ScopeGroup` / `GroupContext`). A `DEPARTMENT_ALL` schedule staffs each subteam to *its own* band, so each group plans against its own roster and its own minimum and maximum; subteam-scoped and department-only are the one-group case.

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

## In-app feedback

`FeedbackService` (`service/feedback/`) turns a report from the help page into a **GitHub issue** (`POST /api/v1/feedback`, `GET /feedback/config`). `settings.feedback_github_token` + `feedback_github_repo` drive it and both default to `None` (prefixed deliberately: a bare `GITHUB_TOKEN` in `.envrc` would override the `gh` CLI's own credentials in every shell opened here): with either unset `is_enabled` is false, the endpoint says so and the frontend hides the form, so a checkout with no token still runs.

- **The tracker is public.** The issue body identifies the reporter by `worker.id` and role — never a name, email or phone. `test_feedback_service.py` asserts the absence of all three; keep it that way if you extend the payload.
- **What the reporter typed goes in a code fence**, sized by `_fence_for` to be longer than any backtick run inside it. Unfenced, `@name` pings a real GitHub account and `#48` cross-links a real PR, so a volunteer could notify strangers by accident.
- Rate limiting is a module-level dict guarded by a lock (`feedback_max_per_hour`), module-level because the service is constructed per request. It is per-process and resets on restart — enough for a stuck Send button, not an audit trail. A table is the upgrade if that ever matters.
- The report's "where did it happen" is a **select the reporter picks from**, not a captured route: people open Help after hitting the problem, so the previous route is a guess. Browser, viewport and build hash are captured (`browserContext()` in `api/feedback.js`); the build hash comes from `vite.config.js` stamping `import.meta.env.VITE_APP_VERSION` from `git rev-parse`, guarded so a tarball build still succeeds.

## Reminders & SMS

`ReminderService` (`service/reminders/`) owns the app's only APScheduler `BackgroundScheduler`, started from the `lifespan` hook with **three jobs**:

- `assignment_notices` — interval, every `settings.notice_interval_minutes` (default 10). The "you have been scheduled" message, sent as soon after generation as the interval allows.
- `daily_reminders` — cron at `settings.reminder_hour` (default 8). The pre-service reminders, one per lead time in `schedules.reminder_days_before`.
- `availability_prompts` — cron at the same hour, and only on an instance that was given a `prompt_service`. `main.py`'s `create_reminder_service` passes one; the `get_reminder_service` DI factory behind the manual-trigger endpoints does not and never starts a scheduler, which is what the `if self.prompt_service` guard in `start()` is for.

`trigger_manually` / `trigger_notices` / `trigger_for_schedule` force a run. SMS goes through `SMSService` (`service/sms/`, Twilio).

**A duty is announced at least twice, by two different paths.** The notice fires minutes after a rota is generated and is tracked by `schedule_assignments.notice_sent_at`; the reminders fire at each lead time in the schedule's ladder. **Both sweeps group by worker** — somebody rostered onto every Sunday of a month gets one notice, not five, and one reminder per day a lead time falls due however many duties it covers. `mark_notice_sent` marks a whole batch in a single statement, so a crash mid-run cannot re-announce half of it.

**`reminder_days_before` is a `smallint[]`, and a send is a row.** `{7,3,1}` is a week out, three days out and the night before; `{}` is allowed and means no reminders at all, only the notice. A single `reminder_sent_at` timestamp could not say "the 7-day one went out, the 3-day one has not", so `20260918092000_multiple_schedule_reminders.sql` replaced it with `assignment_reminder_sends (assignment_id, days_before, sent_at)`. Three consequences to keep:

- The composite primary key *is* the once-only guarantee, the index the RPC's `NOT EXISTS` probes, and — being non-partial — a legal `on_conflict` target, so `mark_reminders_sent` is an idempotent upsert. It is the other side of the 42P10 trap above.
- **`get_assignments_due_for_reminder` returns one row per (assignment, lead time)** and its first column is `assignment_id`, not `id`. The rename is deliberate: left as `id`, `AssignmentResponse.model_validate` would keep succeeding and hand back duplicates that each mark the whole assignment reminded. `DueReminder` is its model, and `days_before` has to survive the round trip because it is half the key the send is recorded under.
- **`trigger_for_schedule` records nothing** (`marks=[]`). It answers no particular lead time, so any `days_before` it wrote would be invented — and an invented one lands on a rung that has not fired yet and cancels it, silently, days later. `test_records_nothing_it_sends` exists so this is not "fixed" back into marking.

`SMSService._describe_duties` carries **no verb** so the notice ("you have been scheduled for ...") and the reminder ("a reminder that you are scheduled for ...") share the one place with the formatting traps in it.

`send_assignment_cancelled` is the third message and the only one with **no retry behind it** — see the editing section above. Like the others its whole body is asserted in `test_sms_service.py`.

**Nobody confirms or declines a duty.** `20260918090000_remove_assignment_confirmation.sql` dropped `schedule_assignments.status`, the `assignment_status` enum, the `/confirm` router and every confirmed/declined display. Asking never closed a loop — nothing reassigned a declined slot, so the one concrete effect of declining was to stop being reminded about a duty still on the rota. Both texts are now statements, and a worker who cannot make a date speaks to their head, who edits the rota. Don't reintroduce a status column as a way to record that.

**`confirmation_tokens` survives the feature it was named for.** It is now purely the per-worker credential behind `/availability/{token}`, whose visitor has no session. `get_or_create_token_id` reuses the live row rather than minting per message, so a link texted last month still opens — which is why `settings.confirmation_token_ttl_days` is measured in days (45) and not hours. `assignment_id` and `last_used_at` are gone; the header comment on `20260402000000_confirmation_tokens.sql` describes a design two migrations dead, so read the table's own `comment on` instead. `/confirm/:token` is kept in `App.jsx` as a redirect to `/availability/:token` so texts already in people's phones still land somewhere useful.

The scheduler runs on its own thread outside the request thread pool — that gap between `request_thread_pool_size` and `db_max_connections` is what reserves connections for it.

**Keep every message body inside GSM-7.** One character outside that alphabet — an em dash, a curly quote, an emoji — switches the whole SMS to UCS-2, which cuts a segment from 160 characters to 70 and so silently doubles or triples the cost of a long roster. Nothing errors; the message just arrives billed as three segments instead of one. `SMSService._describe_duties` uses a plain `-` between groups for exactly this reason, and `test_sms_service.py` asserts the rendered bodies character-by-character against the GSM-7 set. Assert the whole body in a test when you add a message — the multi-date notice once shipped with no separator at all (`dates:Sun 02 Aug...`) because nothing checked the string.

The notice and the confirmation page get their department name by **different routes, and have to**: the notice path goes through the `get_assignments_due_for_notice` RPC, which returns `row_to_json(s)` and so cannot carry an embed, hence `ReminderService._department_name` and its per-run cache; the confirmation page path is a plain PostgREST select and gets `departments(*)` embedded for free. Don't "unify" one into the other without changing the RPC's return signature.

## Frontend architecture

- Routing in `src/App.jsx`; every page is `lazy()`-loaded so each ships as its own chunk. Authenticated routes are wrapped in `ProtectedLayout` (= `ProtectedRoute` + `AppLayout`). Public routes: `/login`, `/reset-password`, `/availability/:token` (mark the dates you cannot serve, reached from an SMS with no session — deliberately token-based because most workers have no login account), and `/confirm/:token`, which now only redirects to it.
- Auth state via `src/context/AuthContext.jsx` (`useAuth()` hook) — exposes `role`, `isAdmin`, `isDepartmentHead` (true for `hod`, `assistant_hod`, **and** `admin`), `signIn`, `signOut`, sourced from the Supabase session's `app_metadata.role`. It carries **no worker id and no department ids** — `auth_user_id` is `exclude=True` on the worker schema, so anything keyed to the signed-in person goes through `GET /account/me` first (`getMyProfile()`), as `useMyDuties` does.
- **`GET /departments` is scoped for heads of department but NOT for plain workers.** The handler branches on `hod`/`assistant_hod` and returns their departments; every other role, `worker` included, falls through to `get_all_departments`. So "the departments I can see" is only a safe basis for a view when gated on `isDepartmentHead` — `DashboardPage` does exactly this, and a worker gets their own duties instead. Don't build a second view on that endpoint without the same gate.
- The dashboard (`src/pages/DashboardPage.jsx` + `src/components/dashboard/`) has **three modes from one layout**: admin and HOD share the department board, differing only in how many departments the API returns, and a worker gets `MyDuties`. Its aggregation lives in `src/lib/dashboard.js`, kept pure and React-free like `lib/rota.js`; `summarizeStaffing` in `src/lib/staffing.js` is the single copy of the how-well-staffed helper that the schedules table and month grid also use, and it takes the **schedule**, not its assignments, because the target it is measured against is stored on the schedule row. There is no whole-church schedule endpoint, so `useDashboard` fans out one `getSchedulesByDepartment` per department; fine at a handful, worth a real endpoint past ~15.
- The help page (`src/pages/HelpPage.jsx`) is one FAQ for everybody: its copy lives in `src/lib/faq.js` (React-free, like `lib/rota.js` and `lib/dashboard.js`), where each section is tagged `audience: 'everyone' | 'heads'` and `faqSectionsFor(isDepartmentHead)` appends the management sections. Heads see the worker questions too — they serve on rotas themselves. Edit the answers there, not in the JSX, and keep them true of the code: they describe how availability is marked, when the cut-off bites, when texts go out, and that a text is a statement rather than a question.
- `src/api/` — one module per domain, all using the shared `apiClient` (`src/api/client.js`), which attaches the bearer token and logs requests/responses **only under `import.meta.env.DEV`**, with sensitive fields stripped by `redact()`. Keep new logging behind that guard.
- `src/hooks/` — one `use<Domain>` hook per domain wrapping the api modules; they own `{ data, loading, error, refetch, ...mutations }` and patch local state after a mutation resolves rather than refetching. Prefer a hook for list/CRUD state; a few pages (`AccountPage`, `ConfirmPage`, `ScheduleDetailPage`, `DepartmentDetailPage`) still call `src/api/` directly for one-off calls.
- UI built with shadcn-style components in `src/components/ui/` + Tailwind, with per-domain component folders. Path alias `@/` → `src/` (see `jsconfig.json` / `vite.config.js`).
- **Theming.** Colour and type follow the church website (newcovenantassembly.ca), whose Elementor kit is the source of the values: purple `#662E91`, red `#C1272D`, gold `#ECCE68`, body grey `#666B68`, heading ink `#0F0F0F`, all in **Epilogue** (self-hosted via `@fontsource-variable/epilogue`). Everything is defined once as HSL triples in the `:root` block of `src/index.css` and exposed through the `@theme` block at the top of the same file — **use the tokens, never a raw palette class** (`bg-green-600`, `text-gray-500`); a `grep -rE "(bg|text|border)-(gray|green|red|amber)-[0-9]" frontend/src/` should stay empty. Three points that are easy to get wrong:
    - `--accent` is shadcn's *hover surface*, not the brand accent. The gold lives in `--highlight` / `--warning`; putting it in `--accent` turns every hover in the app yellow. Gold takes dark ink only — white on it is 1.54:1, and `text-warning` on a light surface is no better, which is why `alert.jsx`'s `warning` variant tints the surface and keeps the text `foreground` where `badge.jsx`'s fills solid.
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

Core tables: `workers`, `worker_app_roles`, `worker_leave`, `departments`, `department_roles`, `worker_departments` (junction, carries `department_role_id` + `subteam_id`), `subteams`, `availability`, `schedules`, `schedule_assignments`, `assignment_reminder_sends`, `department_assistant_hods`, `confirmation_tokens`. RLS helpers defined in SQL: `current_worker_id()`, `has_app_role()`, `is_hod(dept_id)`.

**`worker_departments` is unique on (worker_id, department_id)**, so the role and subteam it carries are facts about *that membership*, not about the person — the same worker holds a different role in another department. Two consequences: `SubteamService.assign_worker` **UPDATEs** that row rather than inserting, so putting somebody in a subteam silently moves them out of whichever one they were in (the add-member dialog says so and labels the button "Move"); and `DepartmentWithWorkersResponse` carries both `department_role` and `subteam` per member, flattened off the junction embed in `DepartmentRepository.get_with_workers` — `test_department_repository_members.py` guards that flatten.

See `docs/database-migrations.md`. When adding tables/columns, also add RLS policies and update the corresponding repository (`queries.py` constants included) + Pydantic schema.

## Testing

`backend/tests/`:

- `unit/services/` — business logic with repositories mocked.
- `unit/test_*.py` — core primitives (`BaseRepository`, filter escaping, redaction, concurrency, JWT verification, phone normalization) and repository query behavior (`test_worker_repository_*.py`, `test_schedule_repository_upcoming.py`).
- `unit/services/test_schedule_planner.py` — the pure monthly planner, no mocks. `unit/test_import_template.py` reads the real `frontend/public/worker-import-sample.csv`, so it fails if template and parser drift apart.
- `integration/routers/` — endpoint behavior; also `test_health.py` and `test_exception_handlers.py`.

`pytest` runs in asyncio auto mode. `tests/conftest.py` provides role-scoped `TestClient` fixtures (`admin_client`, `hod_client`, `worker_client`) that work by overriding `app.dependency_overrides[verify_token]` — that is the way to test authorization, no real tokens involved.

There is no frontend test suite — CI validates the frontend via lint + build.
