"""Streamer protocol definition."""

from typing import Protocol

from app.interfaces.types import StreamResponse
from app.models.user import User


class Streamer(Protocol):
    """Protocol for media streaming handlers."""

    async def stream(
        self,
        user: User,
        file_id: str,
        range_header: str | None,
    ) -> StreamResponse:
        """Generate a streaming response for the requested file and optional Range header."""
        ...
