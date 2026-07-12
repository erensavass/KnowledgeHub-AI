from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import LLMProviderName


class RAGAnswerRequest(BaseModel):
    query: str
    document_ids: list[UUID] | None = None
    top_k: int | None = Field(default=None, ge=1)
    score_threshold: float | None = None
    provider: LLMProviderName | None = None

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be empty")
        return value


class CitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    citation_id: str
    document_id: UUID
    original_filename: str
    chunk_id: UUID
    chunk_index: int
    page_number: int | None
    relevance_score: float
    excerpt: str


class RAGAnswerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    answer: str
    supported: bool
    provider: str
    model: str
    citations: list[CitationResponse]
    source_count: int
    retrieval_metadata: dict[str, Any]
    request_id: UUID
