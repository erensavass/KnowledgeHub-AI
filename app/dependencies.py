from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends
from redis import Redis
from sqlalchemy.orm import Session

from app.application.embedding import EmbeddingService
from app.application.llm import LLMProviderFactory
from app.application.vector_store import VectorStore
from app.core.config import get_settings
from app.infrastructure.cache.redis import get_redis_client
from app.infrastructure.database.session import get_db_session
from app.infrastructure.llm import DefaultLLMProviderFactory
from app.infrastructure.vector.milvus import MilvusVectorStore


def get_database_session() -> Generator[Session, None, None]:
    """FastAPI dependency boundary for future use cases and repositories."""
    yield from get_db_session()


def get_cache_client() -> Redis:
    """FastAPI dependency boundary for future cache-backed use cases."""
    return get_redis_client()


@lru_cache
def get_embedding_service() -> EmbeddingService:
    settings = get_settings()
    return EmbeddingService(
        settings.embedding_model, settings.embedding_device, settings.embedding_batch_size
    )


@lru_cache
def get_vector_store() -> VectorStore:
    settings = get_settings()
    return MilvusVectorStore(
        uri=settings.milvus_uri,
        token=settings.milvus_token,
        collection=settings.milvus_collection,
        metric_type=settings.milvus_metric_type,
        index_type=settings.milvus_index_type,
        hnsw_m=settings.milvus_hnsw_m,
        hnsw_ef_construction=settings.milvus_hnsw_ef_construction,
    )


def get_llm_provider_factory() -> LLMProviderFactory:
    return DefaultLLMProviderFactory(get_settings())


def close_vector_store() -> None:
    if get_vector_store.cache_info().currsize:
        get_vector_store().close()
    get_vector_store.cache_clear()


DatabaseSession = Depends(get_database_session)
CacheClient = Depends(get_cache_client)
