import asyncio
import json
from contextlib import suppress
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError

from app.api.v1.endpoints.auth import DatabaseSession, get_current_user
from app.api.v1.schemas.conversations import (
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationMessageListResponse,
    ConversationMessageRequest,
    ConversationMessageResponse,
    ConversationResponse,
    ConversationUpdateRequest,
)
from app.application.embedding import EmbeddingError, EmbeddingService
from app.application.llm import (
    LLMConfigurationError,
    LLMProviderError,
    LLMProviderFactory,
    LLMTimeoutError,
)
from app.application.prompting import PromptBuilder
from app.application.rag import RAGAnswer, RAGService
from app.application.retrieval import RetrievalService
from app.application.vector_store import VectorStore, VectorStoreError
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.dependencies import get_embedding_service, get_llm_provider_factory, get_vector_store
from app.infrastructure.database.models import (
    Conversation,
    ConversationMessage,
    MessageStatus,
    User,
)
from app.infrastructure.repositories.conversations import ConversationRepository
from app.infrastructure.repositories.documents import DocumentRepository

router = APIRouter(prefix="/conversations", tags=["conversations"])
logger = get_logger(__name__)
CurrentUser = Annotated[User, Depends(get_current_user)]
EmbeddingDependency = Annotated[EmbeddingService, Depends(get_embedding_service)]
VectorStoreDependency = Annotated[VectorStore, Depends(get_vector_store)]
ProviderFactoryDependency = Annotated[LLMProviderFactory, Depends(get_llm_provider_factory)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=255)]


def conversation_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def owned_conversation(
    conversation_id: UUID, user: User, repository: ConversationRepository
) -> Conversation:
    conversation = repository.get_owned(conversation_id, user.id)
    if conversation is None:
        raise conversation_error("conversation_not_found", "Conversation was not found", 404)
    return conversation


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreateRequest, current_user: CurrentUser, session: DatabaseSession
) -> Conversation:
    settings = get_settings()
    title = payload.title or "New conversation"[: settings.conversation_title_max_length]
    if len(title) > settings.conversation_title_max_length:
        raise conversation_error("title_too_long", "Conversation title is too long", 422)
    conversation = Conversation(user_id=current_user.id, title=title)
    result = ConversationRepository(session).create(conversation)
    logger.info(
        "conversation_created",
        extra={"conversation_id": str(result.id), "user_id": str(current_user.id)},
    )
    return result


@router.get("", response_model=ConversationListResponse)
def list_conversations(
    current_user: CurrentUser,
    session: DatabaseSession,
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    include_archived: bool = False,
) -> ConversationListResponse:
    settings = get_settings()
    page_size = limit or settings.conversation_page_size_default
    if page_size > settings.conversation_page_size_max:
        raise conversation_error("page_size_exceeds_limit", "Page size exceeds limit", 422)
    items, total = ConversationRepository(session).list_owned(
        current_user.id, page_size, offset, include_archived
    )
    return ConversationListResponse(items=items, total=total, limit=page_size, offset=offset)


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: UUID, current_user: CurrentUser, session: DatabaseSession
) -> Conversation:
    return owned_conversation(conversation_id, current_user, ConversationRepository(session))


@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdateRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> Conversation:
    settings = get_settings()
    repository = ConversationRepository(session)
    conversation = owned_conversation(conversation_id, current_user, repository)
    if payload.title is not None:
        if len(payload.title) > settings.conversation_title_max_length:
            raise conversation_error("title_too_long", "Conversation title is too long", 422)
        conversation.title = payload.title
    if payload.archived is not None:
        conversation.archived_at = datetime.now(UTC) if payload.archived else None
    result = repository.save(conversation)
    logger.info("conversation_updated", extra={"conversation_id": str(result.id)})
    return result


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: UUID, current_user: CurrentUser, session: DatabaseSession
) -> None:
    repository = ConversationRepository(session)
    conversation = owned_conversation(conversation_id, current_user, repository)
    repository.delete(conversation)
    logger.info("conversation_deleted", extra={"conversation_id": str(conversation_id)})


@router.get("/{conversation_id}/messages", response_model=ConversationMessageListResponse)
def list_messages(
    conversation_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
) -> ConversationMessageListResponse:
    settings = get_settings()
    page_size = limit or settings.conversation_page_size_default
    if page_size > settings.conversation_page_size_max:
        raise conversation_error("page_size_exceeds_limit", "Page size exceeds limit", 422)
    repository = ConversationRepository(session)
    owned_conversation(conversation_id, current_user, repository)
    items, total = repository.list_messages(conversation_id, page_size, offset)
    return ConversationMessageListResponse(items=items, total=total, limit=page_size, offset=offset)


def validate_message_request(
    payload: ConversationMessageRequest,
    current_user: User,
    session: DatabaseSession,
    settings: Settings,
) -> tuple[int, float]:
    if len(payload.query) > settings.message_max_length:
        raise conversation_error("message_too_long", "Message is too long", 422)
    top_k = payload.top_k or settings.search_default_top_k
    if top_k > settings.search_max_top_k:
        raise conversation_error("top_k_exceeds_limit", "top_k exceeds limit", 422)
    if payload.document_ids:
        requested = set(payload.document_ids)
        if (
            DocumentRepository(session).owned_document_ids(list(requested), current_user.id)
            != requested
        ):
            raise conversation_error("document_not_found", "Document was not found", 404)
    threshold = (
        payload.score_threshold
        if payload.score_threshold is not None
        else settings.search_score_threshold
    )
    return top_k, threshold


def build_rag_service(
    session: DatabaseSession,
    embedding_service: EmbeddingService,
    vector_store: VectorStore,
    provider_factory: LLMProviderFactory,
    provider_name: str | None,
    settings: Settings,
) -> RAGService:
    provider = provider_factory.create(provider_name)
    retrieval = RetrievalService(
        DocumentRepository(session), embedding_service, vector_store, settings.embedding_dimension
    )
    return RAGService(
        retrieval,
        PromptBuilder(settings.llm_max_context_chunks, settings.rag_max_context_characters),
        provider,
        settings.llm_temperature,
        settings.llm_request_timeout_seconds,
        settings.rag_citation_excerpt_length,
    )


def replay_or_conflict(
    repository: ConversationRepository, conversation_id: UUID, key: str | None
) -> ConversationMessage | None:
    if not key:
        return None
    replay = repository.idempotency_result(conversation_id, key)
    if replay is None:
        return None
    user_message, assistant = replay
    logger.info(
        "idempotency_replay_detected",
        extra={"conversation_id": str(conversation_id), "request_id": str(user_message.request_id)},
    )
    if assistant is None:
        raise conversation_error("idempotency_request_incomplete", "Request is not completed", 409)
    return assistant


def normalize_idempotency_key(key: str | None) -> str | None:
    if key is None:
        return None
    key = key.strip()
    if not key:
        raise conversation_error("invalid_idempotency_key", "Idempotency key is empty", 422)
    return key


@router.post("/{conversation_id}/messages", response_model=ConversationMessageResponse)
def create_message(
    conversation_id: UUID,
    payload: ConversationMessageRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
    embedding_service: EmbeddingDependency,
    vector_store: VectorStoreDependency,
    provider_factory: ProviderFactoryDependency,
    idempotency_key: IdempotencyKey = None,
) -> ConversationMessage:
    settings = get_settings()
    idempotency_key = normalize_idempotency_key(idempotency_key)
    repository = ConversationRepository(session)
    conversation = owned_conversation(conversation_id, current_user, repository)
    top_k, threshold = validate_message_request(payload, current_user, session, settings)
    replay = replay_or_conflict(repository, conversation_id, idempotency_key)
    if replay is not None:
        return replay
    request_id = uuid4()
    try:
        user_message = repository.start_message(
            conversation_id, payload.query, request_id, idempotency_key
        )
    except IntegrityError:
        session.rollback()
        replay = replay_or_conflict(repository, conversation_id, idempotency_key)
        if replay is not None:
            return replay
        raise
    logger.info(
        "message_request_started",
        extra={"conversation_id": str(conversation_id), "request_id": str(request_id)},
    )
    history = repository.history(
        conversation_id,
        request_id,
        settings.conversation_history_max_messages,
        settings.conversation_history_max_characters,
    )
    logger.info(
        "history_assembled",
        extra={"request_id": str(request_id), "message_count": len(history)},
    )
    try:
        service = build_rag_service(
            session,
            embedding_service,
            vector_store,
            provider_factory,
            payload.provider.value if payload.provider else None,
            settings,
        )
        answer = service.answer(
            payload.query,
            current_user.id,
            payload.document_ids,
            top_k,
            threshold,
            history,
            request_id,
        )
        assistant = repository.complete_message(conversation, user_message, answer)
        logger.info("persistence_completed", extra={"request_id": str(request_id)})
        return assistant
    except (LLMConfigurationError, LLMProviderError, LLMTimeoutError) as exc:
        repository.fail_message(user_message)
        logger.error("generation_failed", extra={"request_id": str(request_id)})
        raise conversation_error("generation_failed", "Message generation failed", 503) from exc
    except (EmbeddingError, VectorStoreError) as exc:
        repository.fail_message(user_message)
        logger.error("generation_failed", extra={"request_id": str(request_id)})
        raise conversation_error("retrieval_unavailable", "Retrieval is unavailable", 503) from exc
    except Exception as exc:
        session.rollback()
        repository.fail_message(user_message)
        logger.error("generation_failed", extra={"request_id": str(request_id)})
        raise conversation_error("message_failed", "Message generation failed", 503) from exc


def sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def message_payload(message: ConversationMessage) -> dict:
    return ConversationMessageResponse.model_validate(message).model_dump(mode="json")


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: UUID,
    payload: ConversationMessageRequest,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
    embedding_service: EmbeddingDependency,
    vector_store: VectorStoreDependency,
    provider_factory: ProviderFactoryDependency,
    idempotency_key: IdempotencyKey = None,
) -> StreamingResponse:
    settings = get_settings()
    idempotency_key = normalize_idempotency_key(idempotency_key)
    repository = ConversationRepository(session)
    conversation = owned_conversation(conversation_id, current_user, repository)
    top_k, threshold = validate_message_request(payload, current_user, session, settings)
    replay = replay_or_conflict(repository, conversation_id, idempotency_key)
    if replay is not None:

        async def replay_events():
            yield sse("request_started", {"request_id": str(replay.request_id), "replay": True})
            yield sse("token", {"token": replay.content})
            yield sse(
                "citations",
                {"citations": message_payload(replay)["citations"]},
            )
            yield sse("completed", {"message": message_payload(replay)})

        return StreamingResponse(replay_events(), media_type="text/event-stream")
    request_id = uuid4()
    user_message = repository.start_message(
        conversation_id, payload.query, request_id, idempotency_key
    )
    history = repository.history(
        conversation_id,
        request_id,
        settings.conversation_history_max_messages,
        settings.conversation_history_max_characters,
    )
    logger.info(
        "message_request_started",
        extra={"conversation_id": str(conversation_id), "request_id": str(request_id)},
    )
    logger.info(
        "history_assembled",
        extra={"request_id": str(request_id), "message_count": len(history)},
    )
    logger.info("streaming_started", extra={"request_id": str(request_id)})

    async def event_stream():
        next_event: asyncio.Task | None = None
        stream = None
        try:
            service = build_rag_service(
                session,
                embedding_service,
                vector_store,
                provider_factory,
                payload.provider.value if payload.provider else None,
                settings,
            )
            stream = service.stream_answer(
                payload.query,
                current_user.id,
                payload.document_ids,
                top_k,
                threshold,
                history,
                request_id,
            )
            while True:
                if next_event is None:
                    next_event = asyncio.create_task(anext(stream))
                done, _ = await asyncio.wait(
                    {next_event}, timeout=settings.stream_heartbeat_seconds
                )
                if not done:
                    if await request.is_disconnected():
                        next_event.cancel()
                        repository.fail_message(user_message)
                        logger.info(
                            "client_disconnected", extra={"request_id": str(request_id)}
                        )
                        return
                    yield ": heartbeat\n\n"
                    continue
                try:
                    event = next_event.result()
                except StopAsyncIteration:
                    break
                finally:
                    next_event = None
                if await request.is_disconnected():
                    repository.fail_message(user_message)
                    logger.info("client_disconnected", extra={"request_id": str(request_id)})
                    return
                if event.event == "citations":
                    continue
                if event.event == "completed":
                    answer: RAGAnswer = event.data["answer"]
                    assistant = repository.complete_message(
                        conversation, user_message, answer
                    )
                    response = message_payload(assistant)
                    yield sse("citations", {"citations": response["citations"]})
                    yield sse("completed", {"message": response})
                    logger.info("persistence_completed", extra={"request_id": str(request_id)})
                    logger.info("streaming_completed", extra={"request_id": str(request_id)})
                    return
                yield sse(event.event, event.data)
                await asyncio.sleep(0)
            raise RuntimeError("stream_completed_without_answer")
        except asyncio.CancelledError:
            repository.fail_message(user_message)
            logger.info("client_disconnected", extra={"request_id": str(request_id)})
            raise
        except Exception:
            session.rollback()
            if user_message.status != MessageStatus.COMPLETED:
                repository.fail_message(user_message)
            logger.error("generation_failed", extra={"request_id": str(request_id)})
            yield sse("error", {"code": "generation_failed", "message": "Generation failed"})
        finally:
            if next_event is not None and not next_event.done():
                next_event.cancel()
                with suppress(asyncio.CancelledError):
                    await next_event
            if stream is not None:
                with suppress(RuntimeError):
                    await stream.aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
