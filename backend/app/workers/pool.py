# pyrefly: ignore [missing-import]
from arq import create_pool
# pyrefly: ignore [missing-import]
from arq.connections import RedisSettings

from app.core.config import settings

_pool = None


async def get_arq_pool():
    # Cached: a fresh Redis connection pool per HTTP request would be wasteful
    # once this runs behind real traffic, not just a one-off verification script.
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings(host=settings.redis_host, port=settings.redis_internal_port))
    return _pool
