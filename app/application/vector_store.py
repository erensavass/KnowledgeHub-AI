from dataclasses import dataclass
from typing import Protocol


class VectorStoreError(Exception):
    """Safe boundary for vector persistence and collection compatibility failures."""


@dataclass(frozen=True)
class VectorEmbedding:
    chunk_id: str
    document_id: str
    user_id: str
    embedding: list[float]
    embedding_model: str
    created_at: int


@dataclass(frozen=True)
class VectorMetadata:
    chunk_id: str
    document_id: str
    embedding_model: str
    embedding_dimension: int


@dataclass(frozen=True)
class VectorSearchResult:
    chunk_id: str
    score: float


class VectorStore(Protocol):
    def ensure_collection(self, dimension: int) -> None: ...

    def upsert_embeddings(self, embeddings: list[VectorEmbedding]) -> None: ...

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None: ...

    def delete_by_document_id(self, document_id: str) -> None: ...

    def has_chunk_vectors(self, chunk_ids: list[str]) -> set[str]: ...

    def count_vectors_for_document(self, document_id: str) -> int: ...

    def list_vector_metadata(self, document_id: str) -> list[VectorMetadata]: ...

    def search(
        self,
        query_vector: list[float],
        user_id: str,
        document_ids: list[str] | None = None,
        top_k: int = 5,
        score_threshold: float | None = None,
    ) -> list[VectorSearchResult]: ...

    def close(self) -> None: ...
