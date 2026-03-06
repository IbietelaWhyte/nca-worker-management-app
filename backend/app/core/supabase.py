from supabase import Client, create_client

from app.core.config import settings

_client: Client | None = None


def get_supabase() -> Client:
    """
    FastAPI dependency that returns a singleton Supabase client.
    Uses the service role key for full DB access from the backend.
    Inject via: client: Client = Depends(get_supabase)
    """
    global _client
    if _client is None:
        _client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
    return _client
