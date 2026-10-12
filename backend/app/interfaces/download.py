"""DownloadEngine protocol definition."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

from app.interfaces.types import Progress, TaskMetadata
from app.models.task import Task


class DownloadEngine(Protocol):
    """Protocol for torrent and direct HTTP download engines."""

    async def fetch_metadata(self, source: str) -> TaskMetadata:
        """Fetch metadata including file list and sizes from the source URI or magnet."""
        ...

    async def start(
        self,
        task: Task,
        selected: list[int],
        dest: Path,
    ) -> AsyncIterator[Progress]:
        """Start downloading selected files to destination directory and yield progress updates."""
        yield Progress(
            task_id="",
            downloaded_bytes=0,
            total_bytes=0,
            speed_bps=0.0,
            state="downloading",
        )

    async def pause(self, task_id: str) -> None:
        """Pause an active download task."""
        ...

    async def resume(self, task_id: str) -> None:
        """Resume a paused download task."""
        ...

    async def cancel(self, task_id: str) -> None:
        """Cancel an active or paused download task."""
        ...

    async def enable_sequential_download(self, task_id: str, file_index: int | None = None) -> bool:
        """Enable sequential piece downloading and prioritize boundary pieces."""
        ...
