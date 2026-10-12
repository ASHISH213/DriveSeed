"""add telegram_chat_id and link token fields to users table

Revision ID: 20261013_07
Revises: 20261012_06
Create Date: 2026-10-13 00:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261013_07"
down_revision: str | None = "20261012_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add telegram integration columns to users table."""
    op.add_column(
        "users",
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_users_telegram_chat_id"),
        "users",
        ["telegram_chat_id"],
        unique=True,
    )

    op.add_column(
        "users",
        sa.Column("telegram_link_token", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_users_telegram_link_token"),
        "users",
        ["telegram_link_token"],
        unique=True,
    )

    op.add_column(
        "users",
        sa.Column("telegram_link_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Drop telegram integration columns from users table."""
    op.drop_column("users", "telegram_link_token_expires_at")
    op.drop_index(op.f("ix_users_telegram_link_token"), table_name="users")
    op.drop_column("users", "telegram_link_token")
    op.drop_index(op.f("ix_users_telegram_chat_id"), table_name="users")
    op.drop_column("users", "telegram_chat_id")
