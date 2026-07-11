from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Document


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
