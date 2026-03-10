.PHONY: install dev run test lint format typecheck clean install-hooks

# Install all dependencies
install:
	uv sync --all-extras

# Install git hooks
install-hooks:
	./scripts/install-hooks.sh

# Run dev server with hot reload
dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run production server
run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port $${PORT:-8000}

# Run tests
test:
	uv run pytest

# Run tests with coverage
test-cov:
	uv run pytest --cov=app --cov-report=term-missing

# Lint
lint:
	uv run ruff check . --fix

# Format
format:
	uv run ruff format .

# Type check
typecheck:
	uv run mypy app

# Run all checks
check: lint format typecheck test

# Clean up
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -name "*.pyc" -delete