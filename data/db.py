from supabase import create_client, Client
from supabase import acreate_client, AsyncClient
from config.config import SUPABASE_URL, SUPABASE_KEY

_sync_client: Client | None = None
_async_client: AsyncClient | None = None


def get_sync_client() -> Client:
    """Get or create the synchronous Supabase client (for Flask routes)."""
    global _sync_client
    if _sync_client is None:
        _sync_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _sync_client


async def get_async_client() -> AsyncClient:
    """Get or create the async Supabase client (for Discord commands)."""
    global _async_client
    if _async_client is None:
        _async_client = await acreate_client(SUPABASE_URL, SUPABASE_KEY)
    return _async_client
