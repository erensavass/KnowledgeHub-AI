"""Establish the Sprint 1 migration baseline.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-11
"""

from collections.abc import Sequence

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """No domain tables exist in Sprint 1."""


def downgrade() -> None:
    """No domain tables exist in Sprint 1."""
