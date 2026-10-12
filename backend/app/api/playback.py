"""Playback API router for media resume positions."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.playback import PlaybackResponse, PlaybackUpdateRequest
from app.services.playback import PlaybackService

router = APIRouter(prefix="/api/playback", tags=["Playback"])


def get_playback_service() -> PlaybackService:
    """Dependency provider returning PlaybackService instance."""
    return PlaybackService()


@router.get("/{file_id}", response_model=PlaybackResponse)
async def get_playback_position(
    file_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    playback_service: Annotated[PlaybackService, Depends(get_playback_service)],
) -> PlaybackResponse:
    """Get last saved playback resume position for a media file."""
    return await playback_service.get_playback(
        db=db,
        user=current_user,
        file_id=file_id,
    )


@router.put("/{file_id}", response_model=PlaybackResponse)
async def update_playback_position(
    file_id: str,
    payload: PlaybackUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    playback_service: Annotated[PlaybackService, Depends(get_playback_service)],
) -> PlaybackResponse:
    """Save or update playback resume position for a media file."""
    return await playback_service.update_playback(
        db=db,
        user=current_user,
        file_id=file_id,
        position_seconds=payload.position_seconds,
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playback_position(
    file_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    playback_service: Annotated[PlaybackService, Depends(get_playback_service)],
) -> None:
    """Clear saved playback resume position for a media file."""
    await playback_service.delete_playback(
        db=db,
        user=current_user,
        file_id=file_id,
    )
