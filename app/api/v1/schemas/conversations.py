from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.v1.schemas.rag import CitationResponse
from app.core.config import LLMProviderName
from app.infrastructure.database.models import MessageRole, MessageStatus


class ConversationCreateRequest(BaseModel):
    title: str | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value


class ConversationUpdateRequest(BaseModel):
    title: str | None = None
    archived: bool | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime
    archived_at: datetime | None


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int
    limit: int
    offset: int


class ConversationMessageRequest(BaseModel):
    query: str
    document_ids: list[UUID] | None = None
    top_k: int | None = Field(default=None, ge=1)
    score_threshold: float | None = None
    provider: LLMProviderName | None = None

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be empty")
        return value


class ConversationMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    status: MessageStatus
    supported: bool | None
    provider: str | None
    model: str | None
    request_id: UUID
    created_at: datetime
    citations: list[CitationResponse]


class ConversationMessageListResponse(BaseModel):
    items: list[ConversationMessageResponse]
    total: int
    limit: int
    offset: int
