"""Media streaming proxy service implementing Range requests and partial content delivery."""

import logging
from collections.abc import AsyncIterator

from app.core.config import Settings, get_settings
from app.interfaces.storage import StorageBackend
from app.interfaces.streamer import Streamer
from app.interfaces.types import StreamResponse
from app.models.user import User
from app.services.drive import DriveApiStorage

logger = logging.getLogger(__name__)


class MediaProxyDisabledError(Exception):
    """Raised when media proxying is requested in a profile where it is disabled (e.g. colab)."""

    def __init__(self, message: str = "Media proxying is disabled in colab profile") -> None:
        super().__init__(message)


async def _empty_iter() -> AsyncIterator[bytes]:
    """Helper empty async generator."""
    if False:
        yield b""


class ProxyStreamer:
    """Production streamer proxying byte ranges directly from StorageBackend."""

    def __init__(
        self,
        settings: Settings | None = None,
        storage: StorageBackend | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._storage = storage

    def _get_storage(self) -> StorageBackend:
        if self._storage is not None:
            return self._storage
        return DriveApiStorage(settings=self.settings)

    async def stream(
        self,
        user: User,
        file_id: str,
        range_header: str | None,
    ) -> StreamResponse:
        """Stream a stored media file supporting HTTP Range requests and 206 Partial Content."""
        if self.settings.PROFILE == "colab":
            raise MediaProxyDisabledError()

        storage = self._get_storage()
        file_meta = await storage.get_file(user, file_id)

        total_size = file_meta.size_bytes
        mime_type = file_meta.mime_type or "application/octet-stream"
        filename = file_meta.name

        base_headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": mime_type,
            "Content-Disposition": f'inline; filename="{filename}"',
        }

        # 1. No Range header -> Full file content (200 OK)
        if not range_header or not range_header.startswith("bytes="):
            content_iter = storage.open_range(
                user, file_id, 0, None if total_size == 0 else total_size - 1
            )
            headers = {
                **base_headers,
                "Content-Length": str(total_size),
            }
            return StreamResponse(
                content_iterator=content_iter,
                status_code=200,
                headers=headers,
            )

        # 2. Parse Range header (e.g., "bytes=0-1023", "bytes=1024-", "bytes=-500")
        raw_range = range_header[len("bytes=") :].strip()
        if "-" not in raw_range:
            return StreamResponse(
                content_iterator=_empty_iter(),
                status_code=416,
                headers={"Content-Range": f"bytes */{total_size}"},
            )

        parts = raw_range.split("-", 1)

        start: int
        end: int

        try:
            if not parts[0]:
                # Suffix byte range: e.g. bytes=-500 -> last 500 bytes
                suffix = int(parts[1])
                if suffix <= 0:
                    raise ValueError("Suffix must be positive")
                start = max(0, total_size - suffix)
                end = total_size - 1
            elif not parts[1]:
                # Open-ended range: e.g. bytes=1024-
                start = int(parts[0])
                end = total_size - 1
            else:
                # Explicit range: e.g. bytes=0-1023
                start = int(parts[0])
                end = int(parts[1])
        except ValueError:
            # Malformed range header -> 416
            return StreamResponse(
                content_iterator=_empty_iter(),
                status_code=416,
                headers={"Content-Range": f"bytes */{total_size}"},
            )

        # 3. Check range bounds
        if total_size == 0 or start >= total_size or start > end or start < 0:
            return StreamResponse(
                content_iterator=_empty_iter(),
                status_code=416,
                headers={"Content-Range": f"bytes */{total_size}"},
            )

        # Clamp end to total_size - 1
        end = min(end, total_size - 1)
        chunk_len = end - start + 1

        headers = {
            **base_headers,
            "Content-Range": f"bytes {start}-{end}/{total_size}",
            "Content-Length": str(chunk_len),
        }

        content_iter = storage.open_range(user, file_id, start, end)

        return StreamResponse(
            content_iterator=content_iter,
            status_code=206,
            headers=headers,
        )


# Static verification of protocol conformance
_conforms: Streamer = ProxyStreamer()
