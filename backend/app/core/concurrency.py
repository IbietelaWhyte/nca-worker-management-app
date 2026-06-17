"""Request concurrency configuration.

Route handlers in this app are synchronous (``def``), so FastAPI runs each one in a worker thread
from anyio's default thread pool. That pool defaults to 40 tokens, but the Supabase client shares a
single httpx connection pool capped at ``settings.db_max_connections``. If more handlers run
concurrently than there are connections, the surplus blocks waiting for a connection and can fail with
a pool timeout.

To keep the configuration internally consistent we cap the request thread pool at
``settings.request_thread_pool_size`` (validated to be <= ``settings.db_max_connections``). Surplus
load then queues cheaply at the thread-pool level instead of erroring on the connection pool. The cap
is per-process, so it holds regardless of how many uvicorn workers are running.
"""

from anyio import to_thread

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def configure_thread_pool() -> None:
    """Cap the request thread pool to the configured size.

    Must be called from within the running event loop (e.g. the app lifespan startup) because the
    default thread limiter is bound to the active async context.
    """
    to_thread.current_default_thread_limiter().total_tokens = settings.request_thread_pool_size
    logger.info("thread_pool_configured", size=settings.request_thread_pool_size)
