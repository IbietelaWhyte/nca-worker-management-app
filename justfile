# Install all dependencies
install:
    cd backend && uv sync --all-extras

# Install git hooks
install-hooks:
    ./scripts/install-hooks.sh

# ---------------------------------------------------------------
# Local database
#
# `npx supabase` rather than a global one: the CLI is pinned in package.json, and a
# globally installed copy is usually a different version. Migrations are version-sensitive
# enough that the pinned one should win.
# ---------------------------------------------------------------

# Start the local Supabase stack. Safe to re-run — it no-ops when already up.
db-start:
    npx supabase start

# Stop the local stack.
db-stop:
    npx supabase stop

# Drop it, recreate it, and reapply every migration from scratch.
db-reset:
    npx supabase db reset

# Print the local stack's URL and keys, ready to paste into .envrc.
db-env:
    npx supabase status -o env

# ---------------------------------------------------------------
# Dev servers
#
# APP_ENV does NOT choose a database. It only feeds Settings.is_production, which gates one
# check on frontend_url. Which database the backend talks to is decided entirely by
# SUPABASE_URL and the three keys beside it — so `dev` below runs against whatever .envrc
# holds, which in most checkouts here is the hosted project.
#
# `dev-local` and `dev-frontend-local` point both halves at the local stack. They come as a
# pair on purpose: the frontend signs in against its own VITE_SUPABASE_URL, so moving only
# the backend leaves it verifying a token minted by a different Supabase, and every request
# 401s.
# ---------------------------------------------------------------

# Run the dev server with hot reload, against the database .envrc points at.
dev: db-start
    cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run the dev server against the LOCAL database, whatever .envrc says.
dev-local: db-start
    #!/usr/bin/env bash
    set -euo pipefail
    status="$(npx supabase status -o env)"
    # Only the four the backend reads. Deliberately not `eval`ing the whole block: it also
    # defines SECRET_KEY, which is Supabase's own and has nothing to do with the app's.
    value() { printf '%s\n' "$status" | sed -nE "s/^$1=\"?([^\"]*)\"?$/\1/p"; }
    export SUPABASE_URL="$(value API_URL)"
    export SUPABASE_ANON_KEY="$(value ANON_KEY)"
    export SUPABASE_SERVICE_ROLE_KEY="$(value SERVICE_ROLE_KEY)"
    export SUPABASE_JWT_SECRET="$(value JWT_SECRET)"
    export APP_ENV=development
    export FRONTEND_URL=http://localhost:5173
    echo "API -> $SUPABASE_URL"
    cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run production server
run:
    cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

# Run tests
test:
    cd backend && uv run pytest

# Run tests with coverage
test-cov:
    cd backend && uv run pytest --cov=app --cov-report=term-missing

# Lint backend and frontend
lint:
    cd backend && uv run ruff check . --fix
    cd frontend && npm run lint

# Format backend and frontend
format:
    cd backend && uv run ruff format .
    cd frontend && npm run format

# Type check
typecheck:
    cd backend && uv run mypy app

# Run all checks
check: lint format typecheck test

# Clean up
clean:
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type d -name .pytest_cache -exec rm -rf {} +
    find . -type d -name .ruff_cache -exec rm -rf {} +
    find . -name "*.pyc" -delete

# Run frontend dev server, against the Supabase frontend/.env points at.
dev-frontend:
    cd frontend && npm run dev

# Run the frontend against the LOCAL stack — the other half of `dev-local`.
dev-frontend-local: db-start
    #!/usr/bin/env bash
    set -euo pipefail
    status="$(npx supabase status -o env)"
    value() { printf '%s\n' "$status" | sed -nE "s/^$1=\"?([^\"]*)\"?$/\1/p"; }
    export VITE_SUPABASE_URL="$(value API_URL)"
    export VITE_SUPABASE_ANON_KEY="$(value ANON_KEY)"
    echo "Auth -> $VITE_SUPABASE_URL"
    cd frontend && npm run dev

# Install frontend dependencies
install-frontend:
    cd frontend && npm install

# Build frontend
build-frontend:
    cd frontend && npm run build
