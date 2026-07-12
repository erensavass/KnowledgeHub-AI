from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.application.vector_store import VectorEmbedding, VectorMetadata, VectorSearchResult
from app.core.config import get_settings
from app.dependencies import get_database_session, get_vector_store
from app.infrastructure.database.base import Base
from app.main import create_application


class FakeVectorStore:
    def __init__(self) -> None:
        self.dimension: int | None = None
        self.vectors: dict[str, VectorEmbedding] = {}
        self.fail_upsert = False
        self.fail_delete = False
        self.fail_search = False
        self.search_results: list[VectorSearchResult] | None = None
        self.last_search: dict[str, object] | None = None

    def ensure_collection(self, dimension: int) -> None:
        if self.dimension is not None and self.dimension != dimension:
            raise RuntimeError("dimension mismatch")
        self.dimension = dimension

    def health_check(self) -> bool:
        return True

    def upsert_embeddings(self, embeddings: list[VectorEmbedding]) -> None:
        if self.fail_upsert:
            from app.application.vector_store import VectorStoreError

            raise VectorStoreError("milvus_upsert_failed")
        self.vectors.update({item.chunk_id: item for item in embeddings})

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        if self.fail_delete:
            from app.application.vector_store import VectorStoreError

            raise VectorStoreError("milvus_delete_failed")
        for chunk_id in chunk_ids:
            self.vectors.pop(chunk_id, None)

    def delete_by_document_id(self, document_id: str) -> None:
        if self.fail_delete:
            from app.application.vector_store import VectorStoreError

            raise VectorStoreError("milvus_delete_failed")
        self.vectors = {
            key: value for key, value in self.vectors.items() if value.document_id != document_id
        }

    def has_chunk_vectors(self, chunk_ids: list[str]) -> set[str]:
        return set(chunk_ids) & self.vectors.keys()

    def count_vectors_for_document(self, document_id: str) -> int:
        return sum(item.document_id == document_id for item in self.vectors.values())

    def list_vector_metadata(self, document_id: str) -> list[VectorMetadata]:
        return [
            VectorMetadata(
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                embedding_model=item.embedding_model,
                embedding_dimension=len(item.embedding),
            )
            for item in self.vectors.values()
            if item.document_id == document_id
        ]

    def search(
        self,
        query_vector: list[float],
        user_id: str,
        document_ids: list[str] | None = None,
        top_k: int = 5,
        score_threshold: float | None = None,
    ) -> list[VectorSearchResult]:
        from app.application.vector_store import VectorStoreError

        if self.fail_search:
            raise VectorStoreError("milvus_search_failed")
        self.last_search = {
            "query_vector": query_vector,
            "user_id": user_id,
            "document_ids": document_ids,
            "top_k": top_k,
            "score_threshold": score_threshold,
        }
        if self.search_results is not None:
            candidates = self.search_results
        else:
            candidates = [
                VectorSearchResult(item.chunk_id, sum(query_vector))
                for item in self.vectors.values()
                if item.user_id == user_id
                and (not document_ids or item.document_id in document_ids)
            ]
        return [
            hit
            for hit in candidates
            if score_threshold is None or hit.score >= score_threshold
        ][:top_k]

    def close(self) -> None:
        pass


@pytest.fixture
def vector_store() -> FakeVectorStore:
    return FakeVectorStore()


@pytest.fixture
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, vector_store: FakeVectorStore
) -> Generator[TestClient, None, None]:
    storage_path = tmp_path / "document-storage"
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(storage_path))
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "3")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    application = create_application()
    application.dependency_overrides[get_database_session] = override_session
    application.dependency_overrides[get_vector_store] = lambda: vector_store
    with TestClient(application) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)
    engine.dispose()
    get_settings.cache_clear()
