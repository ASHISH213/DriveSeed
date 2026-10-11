"""Unit tests for DriveApiStorage using FakeGoogleDriveService."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.interfaces.storage import StorageBackend
from app.models.user import User
from app.services.drive import DriveApiStorage, StorageError, calculate_file_md5
from tests.fakes.fake_google_drive import FakeGoogleDriveService


@pytest.fixture
def mock_user() -> User:
    """Fixture providing a mock User model with encrypted Drive token."""
    return User(
        id=uuid.uuid4(),
        google_sub="google-sub-drive-user",
        email="driveuser@example.com",
        drive_refresh_token_enc="encrypted_drive_token",
        drive_root_folder_id=None,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def fake_drive() -> FakeGoogleDriveService:
    """Fixture providing an in-memory Google Drive API fake."""
    return FakeGoogleDriveService()


@pytest.fixture
def storage(fake_drive: FakeGoogleDriveService) -> DriveApiStorage:
    """Fixture providing DriveApiStorage backed by FakeGoogleDriveService."""
    return DriveApiStorage(
        client_factory=lambda _user: fake_drive,
        chunk_size=512 * 1024,  # 512 KB chunks for fast testing
    )


def test_drive_api_storage_implements_protocol(storage: DriveApiStorage) -> None:
    """Verify DriveApiStorage satisfies StorageBackend interface protocol."""
    assert isinstance(storage, StorageBackend)


@pytest.mark.asyncio
async def test_ensure_root_creates_and_caches_folder(
    storage: DriveApiStorage,
    mock_user: User,
) -> None:
    """Verify ensure_root creates DriveSeed folder and returns the same ID on subsequent calls."""
    root_id = await storage.ensure_root(mock_user)
    assert root_id.startswith("folder_")

    # Second call reuses existing folder
    root_id_2 = await storage.ensure_root(mock_user)
    assert root_id_2 == root_id

    # If cached on user
    mock_user.drive_root_folder_id = root_id
    root_id_3 = await storage.ensure_root(mock_user)
    assert root_id_3 == root_id


@pytest.mark.asyncio
async def test_create_folder(
    storage: DriveApiStorage,
    mock_user: User,
) -> None:
    """Verify create_folder creates subfolder with parent reference."""
    root_id = await storage.ensure_root(mock_user)
    folder_id = await storage.create_folder(mock_user, root_id, "Torrents")

    assert folder_id.startswith("folder_")
    assert folder_id != root_id


@pytest.mark.asyncio
async def test_resumable_upload_with_progress_and_md5(
    storage: DriveApiStorage,
    mock_user: User,
    tmp_path: Path,
) -> None:
    """Verify chunked resumable upload invokes progress callbacks and validates MD5."""
    root_id = await storage.ensure_root(mock_user)

    # Create a 2 MB test file
    test_file = tmp_path / "sample_video.mp4"
    sample_content = b"DriveSeed Test File Chunk Content\n" * 65536
    test_file.write_bytes(sample_content)
    expected_size = len(sample_content)
    expected_md5 = calculate_file_md5(test_file)

    progress_events: list[tuple[int, int]] = []

    def on_progress(bytes_uploaded: int, total_bytes: int) -> None:
        progress_events.append((bytes_uploaded, total_bytes))

    stored_file = await storage.upload_file(
        user=mock_user,
        parent_id=root_id,
        local_path=test_file,
        on_progress=on_progress,
    )

    assert stored_file.id.startswith("gdrive_file_")
    assert stored_file.name == "sample_video.mp4"
    assert stored_file.size_bytes == expected_size
    assert stored_file.md5 == expected_md5

    # Verify multiple chunk progress updates were emitted
    assert len(progress_events) >= 2
    last_event = progress_events[-1]
    assert last_event[0] == expected_size
    assert last_event[1] == expected_size


@pytest.mark.asyncio
async def test_upload_checksum_mismatch_raises_error_and_deletes_file(
    storage: DriveApiStorage,
    fake_drive: FakeGoogleDriveService,
    mock_user: User,
    tmp_path: Path,
) -> None:
    """Verify checksum mismatch deletes corrupted file from Drive and raises StorageError."""
    root_id = await storage.ensure_root(mock_user)
    test_file = tmp_path / "corrupt_test.bin"
    test_file.write_bytes(b"hello corrupted world")

    # Instruct fake to return corrupted MD5
    fake_drive.files().simulate_checksum_mismatch = True

    with pytest.raises(StorageError) as exc_info:
        await storage.upload_file(
            user=mock_user,
            parent_id=root_id,
            local_path=test_file,
            on_progress=lambda _c, _t: None,
        )

    assert exc_info.value.code == "checksum_mismatch"
    # Ensure deleted from remote store
    assert len(fake_drive.files().deleted_ids) >= 1


@pytest.mark.asyncio
async def test_folder_listing_rename_move_delete_and_quota(
    storage: DriveApiStorage,
    mock_user: User,
    tmp_path: Path,
) -> None:
    """Verify list_folder, rename, move, delete, and quota methods."""
    root_id = await storage.ensure_root(mock_user)
    subfolder_id = await storage.create_folder(mock_user, root_id, "Downloads")

    # Upload a file into subfolder
    test_file = tmp_path / "doc.pdf"
    test_file.write_bytes(b"%PDF-1.4 dummy pdf document content")
    stored = await storage.upload_file(
        user=mock_user,
        parent_id=subfolder_id,
        local_path=test_file,
        on_progress=lambda _c, _t: None,
    )

    # 1. list_folder
    items = await storage.list_folder(mock_user, subfolder_id)
    assert len(items) == 1
    assert items[0].id == stored.id
    assert items[0].name == "doc.pdf"

    # 2. rename
    renamed = await storage.rename(mock_user, stored.id, "renamed_doc.pdf")
    assert renamed.name == "renamed_doc.pdf"

    # 3. move
    moved = await storage.move(mock_user, stored.id, root_id)
    assert moved.parent_id == root_id

    # 4. delete
    await storage.delete(mock_user, stored.id)
    items_after_delete = await storage.list_folder(mock_user, root_id)
    assert not any(it.id == stored.id for it in items_after_delete)

    # 5. quota
    user_quota = await storage.quota(mock_user)
    assert user_quota.used_bytes == 1024 * 1024 * 500
    assert user_quota.total_bytes == 15 * 1024 * 1024 * 1024

    # 6. open_range
    chunks = [chunk async for chunk in storage.open_range(mock_user, subfolder_id, 0, 100)]
    assert len(chunks) == 1
    assert chunks[0] == b"fake_media_bytes_data"
