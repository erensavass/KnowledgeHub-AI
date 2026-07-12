"""Add composite indexes for user lists and message pagination.

Revision ID: 0007_release_indexes
Revises: 0006_conversations
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_release_indexes"
down_revision: str | None = "0006_conversations"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_documents_user_created", "documents", ["user_id", "created_at"])
    op.create_index(
        "ix_conversations_user_last_message", "conversations", ["user_id", "last_message_at"]
    )
    op.create_index(
        "ix_messages_conversation_created",
        "conversation_messages",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_created", table_name="conversation_messages")
    op.drop_index("ix_conversations_user_last_message", table_name="conversations")
    op.drop_index("ix_documents_user_created", table_name="documents")
