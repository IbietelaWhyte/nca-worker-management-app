import httpx
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

from app.core.config import settings

_client: Client | None = None


def get_supabase() -> Client:
    """
    FastAPI dependency that returns a singleton Supabase client.
    Uses the service role key for full DB access from the backend.
    Inject via: client: Client = Depends(get_supabase)

    The connection budget is sized in tandem with the request thread pool (see
    `core/concurrency.py` and the `DB_*` / `REQUEST_THREAD_POOL_SIZE` settings): the thread pool stays
    <= `db_max_connections` so every concurrent handler can acquire a connection without waiting on the
    pool timeout. HTTP/2 stays disabled as a known supabase-py/h2 stability workaround.
    """
    global _client
    if _client is None:
        httpx_client = httpx.Client(
            http2=False,  # supabase-py/h2 stability workaround; HTTP/1.1 is sufficient here
            limits=httpx.Limits(
                max_connections=settings.db_max_connections,
                max_keepalive_connections=settings.db_max_keepalive_connections,
                keepalive_expiry=30.0,  # Close idle connections after 30s
            ),
            timeout=httpx.Timeout(
                connect=10.0,  # Connection timeout
                read=30.0,  # Read timeout
                write=10.0,  # Write timeout
                pool=settings.db_pool_timeout,  # Max wait for a free connection from the pool
            ),
        )

        _client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
            options=SyncClientOptions(
                httpx_client=httpx_client,
            ),
        )
    return _client
