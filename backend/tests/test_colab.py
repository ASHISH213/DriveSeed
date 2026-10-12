"""Tests for Google Colab profile implementations (M6).

Verifies MountedDriveStorage, InProcessQueue, DriveHandoffStreamer, single-user auth,
/api/capabilities, and hard rule enforcement (torrent engine disabled, media proxy forbidden).
"""

import hashlib
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import get_current_user
from app.core.config import Settings
from app.interfaces.types import StorageQuota
from app.main import create_app
from app.models.user import User
from app.schemas.task import TaskCreateRequest
from app.services.factory import get_storage_backend, get_task_queue
from app.services.handoff_streamer import DriveHandoffStreamer
from app.services.inprocess_queue import InProcessQueue
from app.services.mounted_drive import MountedDriveStorage
from app.services.task import TaskService
from app.services.torrent import TorrentEngine


@pytest.fixture
def colab_storage_dir(tmp_path: Path) -> Path:
    """Fixture providing a temporary directory simulating mounted Google Drive."""
    storage_path = tmp_path / "MyDrive" / "DriveSeed"
    storage_path.mkdir(parents=True, exist_ok=True)
    return storage_path


@pytest.fixture
def colab_user() -> User:
    """Fixture providing local Colab user model."""
    return User(
        id=uuid.uuid4(),
        email="colab@localhost",
        google_sub="colab-local-owner",
        drive_root_folder_id="root",
    )


# ==============================================================================
# 1. MountedDriveStorage Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_mounted_drive_ensure_root_and_create_folder(
    colab_storage_dir: Path, colab_user: User
) -> None:
    storage = MountedDriveStorage(root_path=colab_storage_dir)

    root_id = await storage.ensure_root(colab_user)
    assert root_id == "root"
    assert colab_storage_dir.exists()

    folder_id = await storage.create_folder(colab_user, "root", "Movies")
    assert folder_id == "Movies"
    assert (colab_storage_dir / "Movies").is_dir()

    nested_id = await storage.create_folder(colab_user, folder_id, "Action")
    assert nested_id == "Movies/Action"
    assert (colab_storage_dir / "Movies" / "Action").is_dir()


@pytest.mark.asyncio
async def test_mounted_drive_upload_file_atomic_and_checksum(
    colab_storage_dir: Path, colab_user: User, tmp_path: Path
) -> None:
    storage = MountedDriveStorage(root_path=colab_storage_dir)

    # Create dummy local file
    test_content = b"DriveSeed high-speed chunked upload test content " * 1000
    source_file = tmp_path / "test_video.mp4"
    source_file.write_bytes(test_content)
    expected_md5 = hashlib.md5(test_content).hexdigest()

    progress_calls: list[tuple[int, int]] = []

    def on_progress(copied: int, total: int) -> None:
        progress_calls.append((copied, total))

    stored = await storage.upload_file(
        user=colab_user,
        parent_id="root",
        local_path=source_file,
        on_progress=on_progress,
    )

    assert stored.name == "test_video.mp4"
    assert stored.size_bytes == len(test_content)
    assert stored.md5 == expected_md5
    assert (colab_storage_dir / "test_video.mp4").is_file()
    # Ensure temporary file is gone
    assert not (colab_storage_dir / ".test_video.mp4.driveseed_tmp").exists()
    assert len(progress_calls) > 0
    assert progress_calls[-1] == (len(test_content), len(test_content))


@pytest.mark.asyncio
async def test_mounted_drive_path_traversal_defense(colab_storage_dir: Path) -> None:
    storage = MountedDriveStorage(root_path=colab_storage_dir)

    with pytest.raises(ValueError, match="Path traversal detected"):
        storage._resolve_path("../../etc/passwd")

    with pytest.raises(ValueError, match="Path traversal detected"):
        storage._resolve_path("..\\..\\Windows\\System32")


@pytest.mark.asyncio
async def test_mounted_drive_list_get_open_range(colab_storage_dir: Path, colab_user: User) -> None:
    storage = MountedDriveStorage(root_path=colab_storage_dir)

    # Create subfolder and files
    subfolder = colab_storage_dir / "Docs"
    subfolder.mkdir()
    sample_file = colab_storage_dir / "sample.txt"
    sample_file.write_text("Hello DriveSeed Colab Edition", encoding="utf-8")
    # Hidden file (should be ignored in listing)
    (colab_storage_dir / ".hidden_file").write_text("secret", encoding="utf-8")

    items = await storage.list_folder(colab_user, "root")
    names = [i.name for i in items]
    assert "Docs" in names
    assert "sample.txt" in names
    assert ".hidden_file" not in names

    meta = await storage.get_file(colab_user, "sample.txt")
    assert meta.name == "sample.txt"
    assert meta.size_bytes == sample_file.stat().st_size

    # Range read: bytes 6 to 14 -> "DriveSeed"
    chunks: list[bytes] = []
    async for chunk in storage.open_range(colab_user, "sample.txt", start=6, end=14):
        chunks.append(chunk)
    assert b"".join(chunks) == b"DriveSeed"


@pytest.mark.asyncio
async def test_mounted_drive_rename_move_delete_and_quota(
    colab_storage_dir: Path, colab_user: User
) -> None:
    storage = MountedDriveStorage(root_path=colab_storage_dir)

    folder = colab_storage_dir / "FolderA"
    folder.mkdir()
    file_path = folder / "item.txt"
    file_path.write_text("data", encoding="utf-8")

    # Rename
    renamed = await storage.rename(colab_user, "FolderA/item.txt", "renamed.txt")
    assert renamed.name == "renamed.txt"
    assert (folder / "renamed.txt").exists()

    # Move to root
    moved = await storage.move(colab_user, "FolderA/renamed.txt", "root")
    assert moved.name == "renamed.txt"
    assert (colab_storage_dir / "renamed.txt").exists()

    # Delete
    await storage.delete(colab_user, "renamed.txt")
    assert not (colab_storage_dir / "renamed.txt").exists()

    # Quota
    quota = await storage.quota(colab_user)
    assert isinstance(quota, StorageQuota)
    assert quota.total_bytes > 0
    assert quota.used_bytes >= 0


# ==============================================================================
# 2. InProcessQueue Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_inprocess_queue_executes_task() -> None:
    queue = InProcessQueue()
    test_task_id = str(uuid.uuid4())

    with patch(
        "app.workers.pipeline.process_download_task", new_callable=AsyncMock
    ) as mock_pipeline:
        job_id = await queue.enqueue("process_download_task", task_id=test_task_id)
        assert job_id.startswith("job-")

        # Let the event loop run scheduled tasks
        import asyncio

        await asyncio.sleep(0.05)
        mock_pipeline.assert_awaited_once_with(ctx={}, task_id=test_task_id)


# ==============================================================================
# 3. DriveHandoffStreamer Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_drive_handoff_streamer_redirects(colab_user: User) -> None:
    streamer = DriveHandoffStreamer()
    file_id = "1A2B3C4D5E"
    assert streamer.get_handoff_url(file_id) == "https://drive.google.com/file/d/1A2B3C4D5E/view"

    resp = await streamer.stream(colab_user, file_id, range_header=None)
    assert resp.status_code == 303
    assert resp.headers["Location"] == "https://drive.google.com/file/d/1A2B3C4D5E/view"
    assert resp.headers["X-DriveSeed-Handoff"] == "true"


# ==============================================================================
# 4. Colab Profile Hard Rule Enforcement
# ==============================================================================


def test_torrent_engine_strictly_refuses_colab_profile() -> None:
    """AGENTS.md & PRD 18.2: Torrent engine must raise RuntimeError when PROFILE=colab."""
    colab_settings = Settings(PROFILE="colab")
    with pytest.raises(RuntimeError, match="Torrent engine is strictly disabled"):
        TorrentEngine(settings=colab_settings)


@pytest.mark.asyncio
async def test_task_service_refuses_magnet_under_colab(colab_user: User) -> None:
    """Colab profile must reject torrent/magnet creation in TaskService."""
    fake_db = AsyncMock()
    fake_queue = AsyncMock()

    service = TaskService(queue=fake_queue)
    with patch("app.services.task.get_settings", return_value=Settings(PROFILE="colab")):
        with pytest.raises(
            ValueError, match="Torrent downloading is strictly disabled in Colab mode"
        ):
            await service.create_task(
                db=fake_db,
                user=colab_user,
                request=TaskCreateRequest(source_uri="magnet:?xt=urn:btih:abcdef1234567890"),
            )


# ==============================================================================
# 5. /api/capabilities and Profile Factory Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_capabilities_api_server_profile() -> None:
    settings = Settings(PROFILE="server")
    app = create_app(settings=settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile"] == "server"
        assert data["storage_backend"] == "drive_api"
        assert data["features"]["torrent"] is True
        assert data["features"]["streaming"] is True
        assert data["features"]["direct_download"] is True


@pytest.mark.asyncio
async def test_capabilities_api_colab_profile() -> None:
    settings = Settings(PROFILE="colab")
    app = create_app(settings=settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile"] == "colab"
        assert data["storage_backend"] == "mounted"
        assert data["features"]["torrent"] is False
        assert data["features"]["streaming"] is False
        assert data["features"]["direct_download"] is True


@pytest.mark.asyncio
async def test_stream_handoff_api_endpoint(colab_user: User) -> None:
    settings = Settings(PROFILE="colab")
    app = create_app(settings=settings)
    app.dependency_overrides[get_current_user] = lambda: colab_user

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as client:
        resp = await client.get("/api/stream/my_video_123/handoff")
        assert resp.status_code == 303
        assert resp.headers["Location"] == "https://drive.google.com/file/d/my_video_123/view"


def test_factories_return_correct_implementations() -> None:
    colab_settings = Settings(PROFILE="colab")
    server_settings = Settings(PROFILE="server")

    colab_storage = get_storage_backend(colab_settings)
    server_storage = get_storage_backend(server_settings)
    assert isinstance(colab_storage, MountedDriveStorage)
    assert not isinstance(server_storage, MountedDriveStorage)

    colab_queue = get_task_queue(colab_settings)
    assert isinstance(colab_queue, InProcessQueue)
