from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchRequest(BaseModel):
    query: str
    document_ids: list[UUID] | None = None
    top_k: int | None = Field(default=None, ge=1)
    score_threshold: float | None = None

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be empty")
        return value


class SearchResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    score: float
    page_number: int | None
    original_filename: str
    metadata: dict[str, Any] | None


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
