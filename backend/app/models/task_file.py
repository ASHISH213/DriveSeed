"""TaskFile database model."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.task import Task


class TaskFile(Base):
    """File item belonging to a multi-file torrent or single-file download task."""

    __tablename__ = "task_files"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
    selected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
    )
    drive_file_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="files",
    )
