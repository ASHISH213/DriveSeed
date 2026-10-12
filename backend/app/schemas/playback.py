"""Pydantic schemas for media playback resume tracking."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlaybackResponse(BaseModel):
    """Current playback resume status for a file."""

    model_config = ConfigDict(from_attributes=True)

    file_id: str
    position_seconds: float = 0.0
    updated_at: datetime | None = None


class PlaybackUpdateRequest(BaseModel):
    """Payload to save current playback position."""

    position_seconds: float = Field(
        ...,
        ge=0.0,
        description="Current playback progress in seconds",
    )
