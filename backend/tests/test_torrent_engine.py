"""Unit and integration tests for TorrentEngine with Colab guard and selective downloading."""

import contextlib
import tempfile
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.security import encrypt_token
from app.models.task import Task
from app.models.user import User
from app.services.drive import DriveApiStorage
from app.services.torrent import TorrentEngine, TorrentEngineDisabledError
from app.workers.pipeline import process_download_task
from tests.fakes.fake_db import FakeAsyncSession
from tests.fakes.fake_google_drive import FakeGoogleDriveService
from tests.fakes.fake_torrent import FakeTorrentSession


def test_torrent_engine_strictly_refuses_to_start_under_colab_profile() -> None:
    """Hard Rule: TorrentEngine MUST raise TorrentEngineDisabledError when PROFILE=colab."""
    colab_settings = Settings(PROFILE="colab")

    with pytest.raises(TorrentEngineDisabledError, match="strictly disabled"):
        TorrentEngine(settings=colab_settings)


@pytest.mark.asyncio
async def test_fetch_metadata_returns_name_and_file_listing() -> None:
    """Verify fetch_metadata extracts files and sizes from fake torrent session."""
    fake_session = FakeTorrentSession()
    engine = TorrentEngine(
        settings=Settings(PROFILE="server"),
        session_factory=lambda: fake_session,
    )

    magnet_uri = (
        "magnet:?xt=urn:btih:da39a3ee5e6b4b0d3255bfef95601890afd80709&dn=Ubuntu-24.04-desktop.iso"
    )
    metadata = await engine.fetch_metadata(magnet_uri)

    assert metadata.name == "Ubuntu-24.04-desktop.iso"
    assert metadata.total_size_bytes == (1024 * 1024 * 20) + 1024
    assert len(metadata.files) == 2
    assert metadata.files[0].path == "Ubuntu-24.04-desktop.iso"
    assert metadata.files[0].size_bytes == 1024 * 1024 * 20
    assert metadata.files[1].path == "checksums.txt"
    assert metadata.files[1].size_bytes == 1024


@pytest.mark.asyncio
async def test_torrent_download_with_selective_file_priorities() -> None:
    """Verify selective downloading prioritizes selected files and ignores unselected files."""
    fake_session = FakeTorrentSession()
    engine = TorrentEngine(
        settings=Settings(PROFILE="server"),
        session_factory=lambda: fake_session,
    )

    task_id = uuid.uuid4()
    task = Task(
        id=task_id,
        user_id=uuid.uuid4(),
        source_type="magnet",
        source_uri="magnet:?xt=urn:btih:abc&dn=MultiFile",
        name="MultiFile",
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        dest = Path(tmp_dir)

        # Select only file index 0
        progresses = []
        async for p in engine.start(task=task, selected=[0], dest=dest):
            progresses.append(p)

        assert len(progresses) > 0
        assert progresses[-1].state == "completed"

        # Verify handle was assigned priorities: [1, 0]
        assert len(fake_session.handles) == 1
        handle = fake_session.handles[0]
        assert handle.priorities == [1, 0]


@pytest.mark.asyncio
async def test_torrent_pause_resume_and_cancellation() -> None:
    """Verify pause, resume, and cancel control the underlying torrent handle."""
    fake_session = FakeTorrentSession()
    engine = TorrentEngine(
        settings=Settings(PROFILE="server"),
        session_factory=lambda: fake_session,
    )

    task_id = uuid.uuid4()
    task = Task(
        id=task_id,
        user_id=uuid.uuid4(),
        source_type="magnet",
        source_uri="magnet:?xt=urn:btih:abc",
        name="test_cancel",
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        dest = Path(tmp_dir)
        cancelled_seen = False

        gen = engine.start(task=task, selected=[0], dest=dest)
        try:
            async for p in gen:
                if p.state == "downloading" and not cancelled_seen:
                    await engine.pause(str(task_id))
                    handle = engine._handles.get(str(task_id))
                    assert handle is not None
                    assert handle.status().paused is True

                    await engine.resume(str(task_id))
                    assert handle.status().paused is False

                    await engine.cancel(str(task_id))

                if p.state == "cancelled":
                    cancelled_seen = True
                    break
        finally:
            await gen.aclose()

        assert cancelled_seen


@pytest.mark.asyncio
async def test_magnet_task_runs_through_worker_pipeline_to_drive() -> None:
    """Verify legal magnet task runs through pipeline, lands in Drive, and cleans up temp."""
    fake_db = FakeAsyncSession()
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        google_sub="sub-torrent-user",
        email="torrent@example.com",
        drive_refresh_token_enc=encrypt_token("tok"),
        created_at=datetime.now(UTC),
    )
    fake_db.add(user)

    task_id = uuid.uuid4()
    task = Task(
        id=task_id,
        user_id=user_id,
        source_type="magnet",
        source_uri="magnet:?xt=urn:btih:da39a3ee5e6b4b0d3255bfef95601890afd80709&dn=Ubuntu-24.04-desktop.iso",
        name="Ubuntu-24.04-desktop.iso",
        state="queued",
    )
    fake_db.add(task)

    with tempfile.TemporaryDirectory() as temp_dir:
        settings = Settings(TEMP_DOWNLOAD_DIR=temp_dir, PROFILE="server")
        fake_session = FakeTorrentSession()
        torrent_engine = TorrentEngine(settings=settings, session_factory=lambda: fake_session)
        fake_drive = FakeGoogleDriveService()
        storage = DriveApiStorage(client_factory=lambda _u: fake_drive, chunk_size=4096)

        @contextlib.asynccontextmanager
        async def fake_session_factory() -> AsyncGenerator[FakeAsyncSession, None]:
            yield fake_db

        ctx = {
            "db_session_factory": fake_session_factory,
            "settings": settings,
            "torrent_engine": torrent_engine,
            "storage_backend": storage,
        }

        # Create simulated downloaded file in destination to simulate libtorrent completion
        task_temp_folder = Path(temp_dir) / str(task.id)
        task_temp_folder.mkdir(parents=True, exist_ok=True)
        sample_file = task_temp_folder / "Ubuntu-24.04-desktop.iso"
        sample_file.write_bytes(b"Ubuntu 24.04 ISO simulated content" * 100)

        # Execute pipeline
        await process_download_task(ctx, str(task.id))

        # Assert task completed
        assert task.state == "completed"
        assert task.progress == 1.0
        assert task.completed_at is not None

        # Assert file uploaded to Drive
        uploaded_files = [
            f
            for f in fake_drive.files().store.values()
            if f.get("mimeType") != "application/vnd.google-apps.folder"
        ]
        assert len(uploaded_files) == 1
        assert uploaded_files[0]["name"] == "Ubuntu-24.04-desktop.iso"

        # Assert local temp folder is deleted
        assert not task_temp_folder.exists()
