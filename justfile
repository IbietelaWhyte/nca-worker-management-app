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

# Print the local stack's URL and keys (already baked into backend/.env.development).
db-env:
    npx supabase status -o env

# ---------------------------------------------------------------
# Dev servers
#
# Nothing here sets an environment variable, deliberately. APP_ENV chooses which
# credentials file each half reads — backend/.env.$APP_ENV, and Vite's own .env.$mode —
# so the environment lives in files and the justfile only ever runs commands.
# ---------------------------------------------------------------

# Run the dev server with hot reload, starting the local database first.
dev: db-start
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

# Run frontend dev server. Vite reads frontend/.env.development — `dev` is its default mode.
dev-frontend:
    cd frontend && npm run dev

# Install frontend dependencies
install-frontend:
    cd frontend && npm install

# Build frontend
build-frontend:
    cd frontend && npm run build
