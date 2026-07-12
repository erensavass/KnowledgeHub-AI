from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.endpoints.auth import DatabaseSession, get_current_user
from app.api.v1.schemas.search import SearchRequest, SearchResponse
from app.application.embedding import EmbeddingError, EmbeddingService
from app.application.retrieval import RetrievalService
from app.application.vector_store import VectorStore, VectorStoreError
from app.core.config import get_settings
from app.core.metrics import metrics
from app.dependencies import get_embedding_service, get_vector_store
from app.infrastructure.database.models import User
from app.infrastructure.repositories.documents import DocumentRepository

router = APIRouter(tags=["search"])
CurrentUser = Annotated[User, Depends(get_current_user)]
EmbeddingDependency = Annotated[EmbeddingService, Depends(get_embedding_service)]
VectorStoreDependency = Annotated[VectorStore, Depends(get_vector_store)]


def search_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


@router.post("/search", response_model=SearchResponse)
def semantic_search(
    payload: SearchRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
    embedding_service: EmbeddingDependency,
    vector_store: VectorStoreDependency,
) -> SearchResponse:
    metrics.increment("knowledgehub_retrieval_requests_total")
    settings = get_settings()
    top_k = payload.top_k or settings.search_default_top_k
    if top_k > settings.search_max_top_k:
        raise search_error(
            "top_k_exceeds_limit", f"top_k must not exceed {settings.search_max_top_k}", 422
        )
    threshold = (
        payload.score_threshold
        if payload.score_threshold is not None
        else settings.search_score_threshold
    )
    repository = DocumentRepository(session)
    if payload.document_ids:
        requested = set(payload.document_ids)
        if repository.owned_document_ids(list(requested), current_user.id) != requested:
            raise search_error("document_not_found", "Document was not found", 404)
    service = RetrievalService(
        repository, embedding_service, vector_store, settings.embedding_dimension
    )
    try:
        return SearchResponse(
            results=service.search(
                payload.query, current_user.id, payload.document_ids, top_k, threshold
            )
        )
    except EmbeddingError as exc:
        metrics.increment("knowledgehub_retrieval_failures_total")
        raise search_error(
            "query_embedding_failed", "Search is temporarily unavailable", 503
        ) from exc
    except VectorStoreError as exc:
        metrics.increment("knowledgehub_retrieval_failures_total")
        raise search_error(
            "vector_store_unavailable", "Search is temporarily unavailable", 503
        ) from exc
    except Exception as exc:
        metrics.increment("knowledgehub_retrieval_failures_total")
        raise search_error("search_failed", "Search is temporarily unavailable", 503) from exc
