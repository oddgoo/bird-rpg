import threading
from supabase import create_client, Client
from supabase import create_async_client, AsyncClient
from config.config import SUPABASE_URL, SUPABASE_KEY

_async_client: AsyncClient | None = None
_sync_local = threading.local()


def get_sync_client() -> Client:
    """Get or create a thread-local synchronous Supabase client (for Flask routes).

    Uses thread-local storage so each thread gets its own HTTP connection,
    avoiding HTTP/2 connection issues when Flask runs in a separate thread.
    """
    client = getattr(_sync_local, "client", None)
    if client is None:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        _sync_local.client = client
    return client


async def get_async_client() -> AsyncClient:
    """Get or create the async Supabase client (for Discord commands)."""
    global _async_client
    if _async_client is None:
        _async_client = await create_async_client(SUPABASE_URL, SUPABASE_KEY)
    return _async_client
