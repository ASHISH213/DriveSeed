"""Task database model."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Task(Base):
    """Download task entity tracking state, progress, and storage status."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    source_uri: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    info_hash: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
        default="queued",
    )
    progress: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="tasks",
    )
