"""create rss_subscriptions and rss_feed_items tables

Revision ID: 20261012_06
Revises: 20261012_05
Create Date: 2026-10-12 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261012_06"
down_revision: str | None = "20261012_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create rss_subscriptions and rss_feed_items tables."""
    op.create_table(
        "rss_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("filter_regex", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_item_title", sa.String(length=512), nullable=True),
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
        op.f("ix_rss_subscriptions_user_id"),
        "rss_subscriptions",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "rss_feed_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("guid", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["subscription_id"], ["rss_subscriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_rss_feed_items_subscription_id"),
        "rss_feed_items",
        ["subscription_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rss_feed_items_guid"),
        "rss_feed_items",
        ["guid"],
        unique=False,
    )


def downgrade() -> None:
    """Drop rss_feed_items and rss_subscriptions tables."""
    op.drop_index(op.f("ix_rss_feed_items_guid"), table_name="rss_feed_items")
    op.drop_index(op.f("ix_rss_feed_items_subscription_id"), table_name="rss_feed_items")
    op.drop_table("rss_feed_items")

    op.drop_index(op.f("ix_rss_subscriptions_user_id"), table_name="rss_subscriptions")
    op.drop_table("rss_subscriptions")
