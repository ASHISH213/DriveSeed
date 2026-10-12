"""User database model."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.api_token import ApiToken
    from app.models.rss import RssSubscription
    from app.models.task import Task
    from app.models.webhook import WebhookEndpoint


class User(Base):
    """User account entity storing Google auth and Drive root info."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    google_sub: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    drive_refresh_token_enc: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    drive_root_folder_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    telegram_chat_id: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=True,
    )
    telegram_link_token: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=True,
    )
    telegram_link_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    api_tokens: Mapped[list["ApiToken"]] = relationship(
        "ApiToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    webhook_endpoints: Mapped[list["WebhookEndpoint"]] = relationship(
        "WebhookEndpoint",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    rss_subscriptions: Mapped[list["RssSubscription"]] = relationship(
        "RssSubscription",
        back_populates="user",
        cascade="all, delete-orphan",
    )
