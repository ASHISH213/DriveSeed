"""RSS Subscription and Feed Item database models for automated downloads."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class RssSubscription(Base):
    """User-configured RSS feed subscription with regex filtering."""

    __tablename__ = "rss_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    filter_regex: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_item_title: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="rss_subscriptions",
    )
    items: Mapped[list["RssFeedItem"]] = relationship(
        "RssFeedItem",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )


class RssFeedItem(Base):
    """Processed item from an RSS feed used for deduplication."""

    __tablename__ = "rss_feed_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("rss_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    guid: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    subscription: Mapped["RssSubscription"] = relationship(
        "RssSubscription",
        back_populates="items",
    )
