from functools import lru_cache

from redis import Redis

from app.core.config import get_settings


@lru_cache
def get_redis_client() -> Redis:
    """Return the shared, lazily-created Redis client."""
    return Redis.from_url(get_settings().redis_url, decode_responses=True, socket_connect_timeout=2)


def close_redis() -> None:
    if get_redis_client.cache_info().currsize:
        get_redis_client().close()
    get_redis_client.cache_clear()
