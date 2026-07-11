from collections.abc import Generator

from fastapi import Depends
from redis import Redis
from sqlalchemy.orm import Session

from app.infrastructure.cache.redis import get_redis_client
from app.infrastructure.database.session import get_db_session


def get_database_session() -> Generator[Session, None, None]:
    """FastAPI dependency boundary for future use cases and repositories."""
    yield from get_db_session()


def get_cache_client() -> Redis:
    """FastAPI dependency boundary for future cache-backed use cases."""
    return get_redis_client()


DatabaseSession = Depends(get_database_session)
CacheClient = Depends(get_cache_client)
