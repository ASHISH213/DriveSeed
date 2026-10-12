"""Drive handoff streamer implementation for Colab profile."""

from collections.abc import AsyncIterator

from app.interfaces.types import StreamResponse
from app.models.user import User


class DriveHandoffStreamer:
    """Streamer implementation that delegates playback to Google Drive for Colab compliance."""

    def get_handoff_url(self, file_id: str) -> str:
        """Return the Google Drive preview/view URL for the requested file."""
        return f"https://drive.google.com/file/d/{file_id}/view"

    async def stream(
        self,
        user: User,
        file_id: str,
        range_header: str | None,
    ) -> StreamResponse:
        """Refuse in-runtime media proxying and redirect/hand off to Drive's native viewer."""
        handoff_url = self.get_handoff_url(file_id)

        async def _empty_iter() -> AsyncIterator[bytes]:
            if False:
                yield b""

        return StreamResponse(
            content_iterator=_empty_iter(),
            status_code=303,
            headers={
                "Location": handoff_url,
                "X-DriveSeed-Handoff": "true",
            },
        )
