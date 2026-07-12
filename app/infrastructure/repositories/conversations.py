from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.application.history import HistoryMessage
from app.application.rag import RAGAnswer
from app.infrastructure.database.models import (
    Conversation,
    ConversationMessage,
    MessageCitation,
    MessageRole,
    MessageStatus,
)


class ConversationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, conversation: Conversation) -> Conversation:
        self.session.add(conversation)
        self.session.commit()
        self.session.refresh(conversation)
        return conversation

    def get_owned(self, conversation_id: UUID, user_id: UUID) -> Conversation | None:
        return self.session.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )

    def list_owned(
        self, user_id: UUID, limit: int, offset: int, include_archived: bool
    ) -> tuple[list[Conversation], int]:
        predicate = [Conversation.user_id == user_id]
        if not include_archived:
            predicate.append(Conversation.archived_at.is_(None))
        total = self.session.scalar(
            select(func.count()).select_from(Conversation).where(*predicate)
        )
        statement = (
            select(Conversation)
            .where(*predicate)
            .order_by(Conversation.last_message_at.desc(), Conversation.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement)), int(total or 0)

    def save(self, conversation: Conversation) -> Conversation:
        self.session.commit()
        self.session.refresh(conversation)
        return conversation

    def delete(self, conversation: Conversation) -> None:
        self.session.delete(conversation)
        self.session.commit()

    def list_messages(
        self, conversation_id: UUID, limit: int, offset: int
    ) -> tuple[list[ConversationMessage], int]:
        total = self.session.scalar(
            select(func.count())
            .select_from(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
        )
        statement = (
            select(ConversationMessage)
            .options(selectinload(ConversationMessage.citations))
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement)), int(total or 0)

    def history(
        self,
        conversation_id: UUID,
        exclude_request_id: UUID,
        max_messages: int,
        max_characters: int,
    ) -> list[HistoryMessage]:
        statement = (
            select(ConversationMessage)
            .where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.status == MessageStatus.COMPLETED,
                ConversationMessage.request_id != exclude_request_id,
            )
            .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
            .limit(max_messages)
        )
        selected: list[HistoryMessage] = []
        remaining = max_characters
        for message in self.session.scalars(statement):
            if remaining <= 0:
                break
            content = message.content[:remaining]
            if content:
                selected.append(HistoryMessage(message.role.value, content))
                remaining -= len(content)
        selected.reverse()
        return selected

    def idempotency_result(
        self, conversation_id: UUID, key: str
    ) -> tuple[ConversationMessage, ConversationMessage | None] | None:
        user_message = self.session.scalar(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.role == MessageRole.USER,
                ConversationMessage.idempotency_key == key,
            )
        )
        if user_message is None:
            return None
        assistant = self.session.scalar(
            select(ConversationMessage)
            .options(selectinload(ConversationMessage.citations))
            .where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.role == MessageRole.ASSISTANT,
                ConversationMessage.request_id == user_message.request_id,
                ConversationMessage.status == MessageStatus.COMPLETED,
            )
        )
        return user_message, assistant

    def start_message(
        self,
        conversation_id: UUID,
        query: str,
        request_id: UUID,
        idempotency_key: str | None,
    ) -> ConversationMessage:
        message = ConversationMessage(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=query,
            status=MessageStatus.PENDING,
            request_id=request_id,
            idempotency_key=idempotency_key,
            created_at=datetime.now(UTC),
        )
        self.session.add(message)
        self.session.commit()
        self.session.refresh(message)
        return message

    def complete_message(
        self,
        conversation: Conversation,
        user_message: ConversationMessage,
        answer: RAGAnswer,
    ) -> ConversationMessage:
        assistant = ConversationMessage(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=answer.answer,
            status=MessageStatus.COMPLETED,
            supported=answer.supported,
            provider=answer.provider,
            model=answer.model,
            request_id=answer.request_id,
            created_at=datetime.now(UTC),
        )
        assistant.citations = [
            MessageCitation(
                citation_id=item.citation_id,
                document_id=item.document_id,
                chunk_id=item.chunk_id,
                original_filename=item.original_filename,
                chunk_index=item.chunk_index,
                page_number=item.page_number,
                relevance_score=item.relevance_score,
                excerpt=item.excerpt,
            )
            for item in answer.citations
        ]
        user_message.status = MessageStatus.COMPLETED
        conversation.last_message_at = datetime.now(UTC)
        self.session.add(assistant)
        self.session.commit()
        return assistant

    def fail_message(self, user_message: ConversationMessage) -> None:
        user_message.status = MessageStatus.FAILED
        self.session.commit()
