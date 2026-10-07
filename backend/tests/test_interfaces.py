"""Contract tests for application interface protocols and fake implementations."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.interfaces.download import DownloadEngine
from app.interfaces.queue import TaskQueue
from app.interfaces.storage import StorageBackend
from app.interfaces.streamer import Streamer
from app.models.task import Task
from app.models.user import User
from tests.fakes import FakeDownloadEngine, FakeStorageBackend, FakeStreamer, FakeTaskQueue


@pytest.fixture
def test_user() -> User:
    """Fixture providing a dummy User model instance."""
    return User(
        id=uuid.uuid4(),
        google_sub="sub_123",
        email="test@example.com",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def test_task(test_user: User) -> Task:
    """Fixture providing a dummy Task model instance."""
    return Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        source_type="url",
        source_uri="https://example.com/file.iso",
        name="Test ISO",
        state="queued",
        progress=0.0,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_storage_backend_contract(test_user: User, tmp_path: Path) -> None:
    """Verify FakeStorageBackend satisfies StorageBackend contract."""
    storage: StorageBackend = FakeStorageBackend()

    # 1. ensure_root
    root_id = await storage.ensure_root(test_user)
    assert root_id.startswith("root_")

    # 2. create_folder
    folder_id = await storage.create_folder(test_user, root_id, "Downloads")
    assert folder_id.startswith("folder_")

    # 3. upload_file
    sample_file = tmp_path / "sample.txt"
    sample_file.write_bytes(b"Hello DriveSeed Storage!")
    progress_updates: list[tuple[int, int]] = []

    def on_progress(loaded: int, total: int) -> None:
        progress_updates.append((loaded, total))

    stored = await storage.upload_file(test_user, folder_id, sample_file, on_progress)
    assert stored.name == "sample.txt"
    assert stored.size_bytes == len(b"Hello DriveSeed Storage!")
    assert stored.parent_id == folder_id
    assert stored.md5 is not None
    assert len(progress_updates) == 2

    # 4. list_folder
    items = await storage.list_folder(test_user, folder_id)
    assert len(items) == 1
    assert items[0].id == stored.id

    # 5. open_range
    chunks = [chunk async for chunk in storage.open_range(test_user, stored.id, 0, 4)]
    assert b"".join(chunks) == b"Hello"

    # 6. rename
    renamed = await storage.rename(test_user, stored.id, "renamed.txt")
    assert renamed.name == "renamed.txt"

    # 7. move
    moved = await storage.move(test_user, stored.id, root_id)
    assert moved.parent_id == root_id

    # 8. quota
    quota = await storage.quota(test_user)
    assert quota.used_bytes > 0
    assert quota.total_bytes > quota.used_bytes

    # 9. delete
    await storage.delete(test_user, stored.id)
    root_items = await storage.list_folder(test_user, root_id)
    assert len(root_items) == 0


@pytest.mark.asyncio
async def test_download_engine_contract(test_task: Task, tmp_path: Path) -> None:
    """Verify FakeDownloadEngine satisfies DownloadEngine contract."""
    engine: DownloadEngine = FakeDownloadEngine()

    # 1. fetch_metadata
    metadata = await engine.fetch_metadata(test_task.source_uri)
    assert metadata.name == "Simulated Download"
    assert len(metadata.files) == 2
    assert metadata.total_size_bytes > 0

    # 2. start download
    dest_dir = tmp_path / "downloads"
    progress_records = []
    async for prog in engine.start(test_task, [0], dest_dir):
        progress_records.append(prog)

    assert len(progress_records) == 2
    assert progress_records[-1].downloaded_bytes == progress_records[-1].total_bytes
    assert (dest_dir / "movie.mp4").exists()

    # 3. pause / resume / cancel
    task_id = str(test_task.id)
    await engine.pause(task_id)
    await engine.resume(task_id)
    await engine.cancel(task_id)


@pytest.mark.asyncio
async def test_task_queue_contract() -> None:
    """Verify FakeTaskQueue satisfies TaskQueue contract."""
    queue: TaskQueue = FakeTaskQueue()

    job_id = await queue.enqueue("download_job", task_id="123", priority=1)
    assert job_id.startswith("job_")


@pytest.mark.asyncio
async def test_streamer_contract(test_user: User) -> None:
    """Verify FakeStreamer satisfies Streamer contract."""
    streamer: Streamer = FakeStreamer()

    # 1. Full stream
    res_full = await streamer.stream(test_user, "file_123", None)
    assert res_full.status_code == 200
    chunks = [c async for c in res_full.content_iterator]
    full_data = b"".join(chunks)
    assert len(full_data) == 1000

    # 2. Partial range stream
    res_range = await streamer.stream(test_user, "file_123", "bytes=0-99")
    assert res_range.status_code == 206
    assert "Content-Range" in res_range.headers
    range_chunks = [c async for c in res_range.content_iterator]
    assert len(b"".join(range_chunks)) == 100
