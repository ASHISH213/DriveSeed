"""create task_files table

Revision ID: 20261011_02
Revises: 20261007_01
Create Date: 2026-10-11 18:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261011_02"
down_revision: str | None = "20261007_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create task_files table."""
    op.create_table(
        "task_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("drive_file_id", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_files_task_id"), "task_files", ["task_id"], unique=False)


def downgrade() -> None:
    """Drop task_files table."""
    op.drop_index(op.f("ix_task_files_task_id"), table_name="task_files")
    op.drop_table("task_files")
