import pytest
from anyio import to_thread
from pydantic import ValidationError

from app.core.concurrency import configure_thread_pool
from app.core.config import Settings, settings


class TestConfigureThreadPool:
    async def test_sets_limiter_to_configured_size(self):
        limiter = to_thread.current_default_thread_limiter()
        original = limiter.total_tokens
        try:
            configure_thread_pool()
            assert limiter.total_tokens == settings.request_thread_pool_size
        finally:
            limiter.total_tokens = original


class TestPoolSizeInvariant:
    def test_shipped_defaults_satisfy_invariant(self):
        # The request thread pool must never outsize the DB connection pool.
        assert settings.request_thread_pool_size <= settings.db_max_connections

    def test_rejects_thread_pool_larger_than_connections(self):
        # Other required fields are sourced from the environment; we only override the two under test.
        with pytest.raises(ValidationError):
            Settings(request_thread_pool_size=100, db_max_connections=10)
