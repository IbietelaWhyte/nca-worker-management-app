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

    Configured with custom httpx client to handle HTTP/2 connection issues:
    - HTTP/2 disabled (fallback to HTTP/1.1 for better connection stability)
    - Reduced connection pool limits to avoid overwhelming Supabase
    - Conservative timeouts to prevent stale connections
    """
    global _client
    if _client is None:
        # Configure httpx client with connection pooling limits
        # to prevent HTTP/2 ENHANCE_YOUR_CALM (error_code:9) errors
        httpx_client = httpx.Client(
            http2=False,  # Disable HTTP/2, use HTTP/1.1 for more stable connections
            limits=httpx.Limits(
                max_connections=10,  # Limit total connections
                max_keepalive_connections=5,  # Limit persistent connections
                keepalive_expiry=30.0,  # Close idle connections after 30s
            ),
            timeout=httpx.Timeout(
                connect=10.0,  # Connection timeout
                read=30.0,  # Read timeout
                write=10.0,  # Write timeout
                pool=5.0,  # Pool timeout
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
