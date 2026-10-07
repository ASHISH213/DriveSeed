"""In-memory fake implementation of DownloadEngine for tests."""

from collections.abc import AsyncIterator
from pathlib import Path

from app.interfaces.download import DownloadEngine
from app.interfaces.types import Progress, TaskFileMetadata, TaskMetadata
from app.models.task import Task


class FakeDownloadEngine:
    """In-memory download engine simulating torrent and URL downloads."""

    def __init__(self) -> None:
        self.paused_tasks: set[str] = set()
        self.resumed_tasks: set[str] = set()
        self.cancelled_tasks: set[str] = set()

    async def fetch_metadata(self, source: str) -> TaskMetadata:
        """Return simulated file metadata based on source URI."""
        files = [
            TaskFileMetadata(index=0, path="movie.mp4", size_bytes=1024 * 1024 * 500),
            TaskFileMetadata(index=1, path="sample.nfo", size_bytes=1024),
        ]
        return TaskMetadata(
            name="Simulated Download",
            files=files,
            total_size_bytes=sum(f.size_bytes for f in files),
        )

    async def start(
        self,
        task: Task,
        selected: list[int],
        dest: Path,
    ) -> AsyncIterator[Progress]:
        """Simulate chunked download yielding progress objects."""
        dest.mkdir(parents=True, exist_ok=True)
        # Create a dummy downloaded file
        sample_file = dest / "movie.mp4"
        sample_file.write_bytes(b"dummy movie content" * 100)

        total_bytes = 1000
        yield Progress(
            task_id=str(task.id),
            downloaded_bytes=500,
            total_bytes=total_bytes,
            speed_bps=50000.0,
            state="downloading",
        )
        yield Progress(
            task_id=str(task.id),
            downloaded_bytes=total_bytes,
            total_bytes=total_bytes,
            speed_bps=50000.0,
            state="downloading",
        )

    async def pause(self, task_id: str) -> None:
        """Record task as paused."""
        self.paused_tasks.add(task_id)

    async def resume(self, task_id: str) -> None:
        """Record task as resumed."""
        self.paused_tasks.discard(task_id)
        self.resumed_tasks.add(task_id)

    async def cancel(self, task_id: str) -> None:
        """Record task as cancelled."""
        self.cancelled_tasks.add(task_id)


# Type assertion for static protocol conformance
_conforms: DownloadEngine = FakeDownloadEngine()
