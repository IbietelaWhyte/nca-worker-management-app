# Install all dependencies
install:
    cd backend && uv sync --all-extras

# Install git hooks
install-hooks:
    ./install-hooks.sh

# Run dev server with hot reload
dev:
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

# Run frontend dev server
dev-frontend:
    cd frontend && npm run dev

# Install frontend dependencies
install-frontend:
    cd frontend && npm install

# Build frontend
build-frontend:
    cd frontend && npm run build
