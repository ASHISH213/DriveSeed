"""Playback service for persisting and retrieving user media playback positions."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playback import Playback
from app.models.user import User
from app.schemas.playback import PlaybackResponse


class PlaybackService:
    """Service encapsulating playback state persistence and retrieval."""

    async def get_playback(
        self,
        db: AsyncSession,
        user: User,
        file_id: str,
    ) -> PlaybackResponse:
        """Retrieve playback resume position for a given file.

        Returns 0.0 seconds if no prior playback recorded.
        """
        stmt = select(Playback).where(
            Playback.user_id == user.id,
            Playback.file_id == file_id,
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            return PlaybackResponse(
                file_id=file_id,
                position_seconds=0.0,
                updated_at=None,
            )

        return PlaybackResponse(
            file_id=record.file_id,
            position_seconds=record.position_seconds,
            updated_at=record.updated_at,
        )

    async def update_playback(
        self,
        db: AsyncSession,
        user: User,
        file_id: str,
        position_seconds: float,
    ) -> PlaybackResponse:
        """Upsert playback resume position for a given file."""
        stmt = select(Playback).where(
            Playback.user_id == user.id,
            Playback.file_id == file_id,
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        now = datetime.now(UTC)
        if record is None:
            record = Playback(
                user_id=user.id,
                file_id=file_id,
                position_seconds=position_seconds,
                updated_at=now,
            )
            db.add(record)
        else:
            record.position_seconds = position_seconds
            record.updated_at = now

        await db.commit()
        await db.refresh(record)

        return PlaybackResponse(
            file_id=record.file_id,
            position_seconds=record.position_seconds,
            updated_at=record.updated_at,
        )

    async def delete_playback(
        self,
        db: AsyncSession,
        user: User,
        file_id: str,
    ) -> bool:
        """Reset or clear playback resume position for a given file."""
        stmt = select(Playback).where(
            Playback.user_id == user.id,
            Playback.file_id == file_id,
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if record is not None:
            await db.delete(record)
            await db.commit()
            return True
        return False
