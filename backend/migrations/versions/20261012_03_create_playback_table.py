"""create playback table

Revision ID: 20261012_03
Revises: 20261011_02
Create Date: 2026-10-12 10:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261012_03"
down_revision: str | None = "20261011_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create playback table."""
    op.create_table(
        "playback",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.String(length=255), nullable=False),
        sa.Column("position_seconds", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "file_id"),
    )
    op.create_index(op.f("ix_playback_user_id"), "playback", ["user_id"], unique=False)


def downgrade() -> None:
    """Drop playback table."""
    op.drop_index(op.f("ix_playback_user_id"), table_name="playback")
    op.drop_table("playback")
