"""Add embedding lifecycle and chunk embedding metadata.

Revision ID: 0005_chunk_embedding_metadata
Revises: 0004_document_processing
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_chunk_embedding_metadata"
down_revision: str | None = "0004_document_processing"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

embedding_status = sa.Enum(
    "pending", "embedding", "embedded", "embedding_failed", name="embedding_status"
)


def upgrade() -> None:
    embedding_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "documents",
        sa.Column(
            "embedding_status", embedding_status, server_default="pending", nullable=False
        ),
    )
    op.add_column("documents", sa.Column("embedding_error_code", sa.String(length=64)))
    op.create_table(
        "chunk_embeddings",
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chunk_id"),
    )


def downgrade() -> None:
    op.drop_table("chunk_embeddings")
    op.drop_column("documents", "embedding_error_code")
    op.drop_column("documents", "embedding_status")
    embedding_status.drop(op.get_bind(), checkfirst=True)
