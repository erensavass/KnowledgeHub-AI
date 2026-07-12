from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from app.application.embedding import EmbeddingService
from app.application.vector_store import VectorStore
from app.core.logging import get_logger

logger = get_logger(__name__)


class RetrievalRepository(Protocol):
    def hydrate_search_chunks(
        self, chunk_ids: list[UUID], user_id: UUID
    ) -> dict[UUID, "RetrievalSource"]: ...


@dataclass(frozen=True)
class RetrievalSource:
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    page_number: int | None
    original_filename: str
    metadata: dict[str, Any] | None


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    score: float
    page_number: int | None
    original_filename: str
    metadata: dict[str, Any] | None


class RetrievalService:
    def __init__(
        self,
        repository: RetrievalRepository,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        embedding_dimension: int,
    ) -> None:
        self.repository = repository
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.embedding_dimension = embedding_dimension

    def search(
        self,
        query: str,
        user_id: UUID,
        document_ids: list[UUID] | None,
        top_k: int,
        score_threshold: float | None,
    ) -> list[RetrievalResult]:
        logger.info(
            "search_started",
            extra={"user_id": str(user_id), "top_k": top_k, "filtered": bool(document_ids)},
        )
        try:
            vector = self.embedding_service.embed([query])[0]
            logger.info("query_embedded", extra={"user_id": str(user_id)})
            self.vector_store.ensure_collection(self.embedding_dimension)
            hits = self.vector_store.search(
                vector,
                str(user_id),
                [str(item) for item in document_ids] if document_ids else None,
                top_k,
                score_threshold,
            )
            logger.info(
                "milvus_search_completed",
                extra={"user_id": str(user_id), "result_count": len(hits)},
            )
            unique_hits = []
            seen: set[UUID] = set()
            for hit in hits:
                try:
                    chunk_id = UUID(hit.chunk_id)
                except ValueError:
                    logger.warning("search_reconciliation_warning", extra={"user_id": str(user_id)})
                    continue
                if chunk_id not in seen:
                    seen.add(chunk_id)
                    unique_hits.append((chunk_id, hit.score))
            hydrated = self.repository.hydrate_search_chunks(
                [chunk_id for chunk_id, _ in unique_hits], user_id
            )
            missing_count = len(unique_hits) - len(hydrated)
            if missing_count:
                logger.warning(
                    "search_reconciliation_warning",
                    extra={"user_id": str(user_id), "missing_count": missing_count},
                )
            results = [
                RetrievalResult(
                    chunk_id=source.chunk_id,
                    document_id=source.document_id,
                    chunk_index=source.chunk_index,
                    content=source.content,
                    score=score,
                    page_number=source.page_number,
                    original_filename=source.original_filename,
                    metadata=source.metadata,
                )
                for chunk_id, score in unique_hits
                if (source := hydrated.get(chunk_id)) is not None
            ]
            logger.info(
                "results_hydrated",
                extra={"user_id": str(user_id), "result_count": len(results)},
            )
            logger.info(
                "search_completed",
                extra={"user_id": str(user_id), "result_count": len(results)},
            )
            return results
        except Exception as exc:
            logger.error(
                "search_failed",
                extra={"user_id": str(user_id), "error_type": type(exc).__name__},
            )
            raise
