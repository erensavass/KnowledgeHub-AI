from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.application.retrieval import RetrievalSource
from app.infrastructure.database.models import (
    ChunkEmbedding,
    Document,
    DocumentChunk,
    EmbeddingStatus,
)


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, document: Document) -> Document:
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document

    def list_for_user(self, user_id: UUID) -> list[Document]:
        statement = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc(), Document.id.desc())
        )
        return list(self.session.scalars(statement))

    def get_for_user(self, document_id: UUID, user_id: UUID) -> Document | None:
        return self.session.scalar(
            select(Document).where(Document.id == document_id, Document.user_id == user_id)
        )

    def delete(self, document: Document) -> None:
        self.session.delete(document)
        self.session.commit()

    def replace_chunks(self, document_id: UUID, chunks: list[DocumentChunk]) -> None:
        self.session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        self.session.add_all(chunks)

    def list_chunks(
        self, document_id: UUID, limit: int, offset: int
    ) -> tuple[list[DocumentChunk], int]:
        total = self.session.scalar(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.document_id == document_id
            )
        )
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement)), int(total or 0)

    def all_chunks(self, document_id: UUID) -> list[DocumentChunk]:
        return list(
            self.session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
            )
        )

    def embedding_metadata(self, document_id: UUID) -> list[ChunkEmbedding]:
        statement = (
            select(ChunkEmbedding)
            .join(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        return list(self.session.scalars(statement))

    def replace_embedding_metadata(
        self, chunk_ids: list[UUID], metadata: list[ChunkEmbedding]
    ) -> None:
        if chunk_ids:
            self.session.execute(
                delete(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(chunk_ids))
            )
        self.session.add_all(metadata)

    def owned_document_ids(self, document_ids: list[UUID], user_id: UUID) -> set[UUID]:
        statement = select(Document.id).where(
            Document.id.in_(document_ids), Document.user_id == user_id
        )
        return set(self.session.scalars(statement))

    def hydrate_search_chunks(
        self, chunk_ids: list[UUID], user_id: UUID
    ) -> dict[UUID, RetrievalSource]:
        if not chunk_ids:
            return {}
        statement = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .where(
                DocumentChunk.id.in_(chunk_ids),
                Document.user_id == user_id,
                Document.embedding_status == EmbeddingStatus.EMBEDDED,
            )
        )
        return {
            chunk.id: RetrievalSource(
                chunk_id=chunk.id,
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_number=chunk.page_number,
                original_filename=document.original_filename,
                metadata=chunk.metadata_json,
            )
            for chunk, document in self.session.execute(statement)
        }
