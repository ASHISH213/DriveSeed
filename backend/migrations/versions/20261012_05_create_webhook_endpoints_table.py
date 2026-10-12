"""create webhook_endpoints table

Revision ID: 20261012_05
Revises: 20261012_04
Create Date: 2026-10-12 18:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261012_05"
down_revision: str | None = "20261012_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create webhook_endpoints table."""
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("secret", sa.String(length=255), nullable=False),
        sa.Column(
            "events",
            sa.String(length=255),
            nullable=False,
            server_default="task.completed,task.failed",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_webhook_endpoints_user_id"),
        "webhook_endpoints",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop webhook_endpoints table."""
    op.drop_index(op.f("ix_webhook_endpoints_user_id"), table_name="webhook_endpoints")
    op.drop_table("webhook_endpoints")
