from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.infrastructure.database.models import DocumentStatus, EmbeddingStatus


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    original_filename: str
    stored_filename: str
    mime_type: str
    size_bytes: int
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None
    chunk_count: int
    processing_error_code: str | None
    embedding_status: EmbeddingStatus
    embedding_error_code: str | None


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    character_count: int
    token_count: int
    page_number: int | None
    metadata_json: dict | None
    created_at: datetime


class ChunkListResponse(BaseModel):
    items: list[DocumentChunkResponse]
    total: int
    limit: int
    offset: int


class EmbedResponse(BaseModel):
    document_id: UUID
    total_chunks: int
    embedded_chunks: int
    skipped_chunks: int
    embedding_model: str
    status: EmbeddingStatus


class EmbeddingStatusResponse(BaseModel):
    total_chunks: int
    embedded_chunks_in_postgres: int
    vectors_in_milvus: int
    remaining_chunks: int
    embedding_model: str
    embedding_dimension: int
    status: EmbeddingStatus
    consistent: bool
