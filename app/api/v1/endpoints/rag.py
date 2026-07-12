from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.endpoints.auth import DatabaseSession, get_current_user
from app.api.v1.schemas.rag import RAGAnswerRequest, RAGAnswerResponse
from app.application.embedding import EmbeddingError, EmbeddingService
from app.application.llm import (
    LLMConfigurationError,
    LLMProviderError,
    LLMProviderFactory,
    LLMTimeoutError,
)
from app.application.prompting import PromptBuilder
from app.application.rag import RAGService
from app.application.retrieval import RetrievalService
from app.application.vector_store import VectorStore, VectorStoreError
from app.core.config import get_settings
from app.dependencies import (
    get_embedding_service,
    get_llm_provider_factory,
    get_vector_store,
)
from app.infrastructure.database.models import User
from app.infrastructure.repositories.documents import DocumentRepository

router = APIRouter(prefix="/rag", tags=["rag"])
CurrentUser = Annotated[User, Depends(get_current_user)]
EmbeddingDependency = Annotated[EmbeddingService, Depends(get_embedding_service)]
VectorStoreDependency = Annotated[VectorStore, Depends(get_vector_store)]
ProviderFactoryDependency = Annotated[LLMProviderFactory, Depends(get_llm_provider_factory)]


def rag_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


@router.post("/answer", response_model=RAGAnswerResponse)
def answer_question(
    payload: RAGAnswerRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
    embedding_service: EmbeddingDependency,
    vector_store: VectorStoreDependency,
    provider_factory: ProviderFactoryDependency,
) -> RAGAnswerResponse:
    settings = get_settings()
    if len(payload.query) > settings.rag_max_query_length:
        raise rag_error(
            "query_too_long",
            f"query must not exceed {settings.rag_max_query_length} characters",
            422,
        )
    top_k = payload.top_k or settings.search_default_top_k
    if top_k > settings.search_max_top_k:
        raise rag_error(
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
            raise rag_error("document_not_found", "Document was not found", 404)
    try:
        provider = provider_factory.create(payload.provider.value if payload.provider else None)
        retrieval = RetrievalService(
            repository, embedding_service, vector_store, settings.embedding_dimension
        )
        service = RAGService(
            retrieval,
            PromptBuilder(
                settings.llm_max_context_chunks, settings.rag_max_context_characters
            ),
            provider,
            settings.llm_temperature,
            settings.llm_request_timeout_seconds,
            settings.rag_citation_excerpt_length,
        )
        return RAGAnswerResponse(
            **service.answer(
                payload.query, current_user.id, payload.document_ids, top_k, threshold
            ).__dict__
        )
    except LLMConfigurationError as exc:
        raise rag_error(
            "llm_provider_not_configured", "LLM provider is not configured", 503
        ) from exc
    except LLMTimeoutError as exc:
        raise rag_error("llm_request_timed_out", "Answer generation timed out", 504) from exc
    except LLMProviderError as exc:
        raise rag_error(
            "llm_provider_unavailable", "Answer generation is unavailable", 502
        ) from exc
    except (EmbeddingError, VectorStoreError) as exc:
        raise rag_error(
            "retrieval_unavailable", "Retrieval is temporarily unavailable", 503
        ) from exc
    except Exception as exc:
        raise rag_error("rag_failed", "Answer generation is temporarily unavailable", 503) from exc
