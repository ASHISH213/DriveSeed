"""In-memory fake implementation of Streamer for tests."""

from collections.abc import AsyncIterator

from app.interfaces.streamer import Streamer
from app.interfaces.types import StreamResponse
from app.models.user import User


class FakeStreamer:
    """In-memory streaming service handling Range headers and partial content."""

    def __init__(self) -> None:
        self.sample_data = b"0123456789" * 100  # 1000 bytes

    async def stream(
        self,
        user: User,
        file_id: str,
        range_header: str | None,
    ) -> StreamResponse:
        """Return StreamResponse simulating full or 206 Partial Content delivery."""
        total_len = len(self.sample_data)

        if range_header and range_header.startswith("bytes="):
            byte_range = range_header.split("=")[1]
            parts = byte_range.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else total_len - 1
            chunk = self.sample_data[start : end + 1]

            async def _range_gen() -> AsyncIterator[bytes]:
                yield chunk

            return StreamResponse(
                content_iterator=_range_gen(),
                status_code=206,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{total_len}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(len(chunk)),
                    "Content-Type": "video/mp4",
                },
            )

        async def _full_gen() -> AsyncIterator[bytes]:
            yield self.sample_data

        return StreamResponse(
            content_iterator=_full_gen(),
            status_code=200,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(total_len),
                "Content-Type": "video/mp4",
            },
        )


# Type assertion for static protocol conformance
_conforms: Streamer = FakeStreamer()
