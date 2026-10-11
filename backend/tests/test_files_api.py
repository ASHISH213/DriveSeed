"""Tests for Library Files API: browsing, search, folder creation, rename, move, and delete."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.files import get_library_service
from app.core.db import get_db_session
from app.core.security import create_session_token, encrypt_token
from app.interfaces.types import StoredFile
from app.main import create_app
from app.models.user import User
from app.services.library import LibraryService
from tests.fakes.fake_db import FakeAsyncSession
from tests.fakes.fake_storage import FakeStorageBackend


@pytest.fixture
def fake_db() -> FakeAsyncSession:
    """Fixture providing in-memory database session."""
    return FakeAsyncSession()


@pytest.fixture
def fake_storage() -> FakeStorageBackend:
    """Fixture providing in-memory fake storage backend."""
    return FakeStorageBackend()


@pytest.fixture
def test_library_service(fake_storage: FakeStorageBackend) -> LibraryService:
    """Fixture providing LibraryService with fake storage."""
    return LibraryService(storage=fake_storage)


@pytest.fixture
def test_user(fake_db: FakeAsyncSession) -> User:
    """Fixture providing an authenticated user with connected Google Drive."""
    user = User(
        id=uuid.uuid4(),
        google_sub="sub-library-user",
        email="library@example.com",
        drive_refresh_token_enc=encrypt_token("mock-refresh-token"),
        drive_root_folder_id=None,
        created_at=datetime.now(UTC),
    )
    fake_db.add(user)
    return user


@pytest.fixture
def app_with_library(
    fake_db: FakeAsyncSession,
    test_library_service: LibraryService,
):
    """FastAPI app instance with overridden db and library service."""
    app = create_app()

    async def override_db() -> AsyncGenerator[FakeAsyncSession, None]:
        yield fake_db

    def override_service() -> LibraryService:
        return test_library_service

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_library_service] = override_service
    return app


@pytest.mark.asyncio
async def test_unauthenticated_files_rejected(app_with_library) -> None:
    """Verify unauthenticated requests to /api/files return 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_library),
        base_url="http://test",
    ) as client:
        res1 = await client.get("/api/files")
        assert res1.status_code == 401
        assert res1.json()["detail"]["error"]["code"] == "unauthorized"

        res2 = await client.post("/api/files/folder", json={"name": "test"})
        assert res2.status_code == 401

        res3 = await client.patch("/api/files/fake-id", json={"name": "new"})
        assert res3.status_code == 401

        res4 = await client.delete("/api/files/fake-id")
        assert res4.status_code == 401


@pytest.mark.asyncio
async def test_drive_not_connected_rejected(
    app_with_library,
    fake_db: FakeAsyncSession,
) -> None:
    """Verify operations fail if user has not linked Google Drive."""
    disconnected_user = User(
        id=uuid.uuid4(),
        google_sub="sub-disconnected",
        email="disconnected@example.com",
        drive_refresh_token_enc=None,  # No Drive token
        drive_root_folder_id=None,
        created_at=datetime.now(UTC),
    )
    fake_db.add(disconnected_user)
    token = create_session_token(user_id=str(disconnected_user.id))

    async with AsyncClient(
        transport=ASGITransport(app=app_with_library),
        base_url="http://test",
        cookies={"driveseed_session": token},
    ) as client:
        res = await client.get("/api/files")
        assert res.status_code == 400
        assert res.json()["detail"]["error"]["code"] == "drive_not_connected"


@pytest.mark.asyncio
async def test_list_empty_library_and_create_folder(
    app_with_library,
    test_user: User,
) -> None:
    """Verify listing root folder and creating subfolders."""
    token = create_session_token(user_id=str(test_user.id))

    async with AsyncClient(
        transport=ASGITransport(app=app_with_library),
        base_url="http://test",
        cookies={"driveseed_session": token},
    ) as client:
        # 1. Initial list -> empty files list, root breadcrumb
        res = await client.get("/api/files")
        assert res.status_code == 200
        data = res.json()
        assert len(data["files"]) == 0
        assert len(data["breadcrumbs"]) == 1
        assert data["breadcrumbs"][0]["name"] == "DriveSeed"
        root_id = data["current_folder_id"]

        # 2. Create subfolder "Movies"
        res2 = await client.post("/api/files/folder", json={"name": "Movies", "parent_id": root_id})
        assert res2.status_code == 201
        folder_data = res2.json()
        assert folder_data["name"] == "Movies"
        assert folder_data["is_folder"] is True
        assert folder_data["parent_id"] == root_id

        # 3. List root -> shows "Movies" folder
        res3 = await client.get("/api/files")
        assert res3.status_code == 200
        data3 = res3.json()
        assert len(data3["files"]) == 1
        assert data3["files"][0]["name"] == "Movies"
        assert data3["files"][0]["is_folder"] is True


@pytest.mark.asyncio
async def test_search_rename_move_and_delete_file(
    app_with_library,
    test_user: User,
    fake_storage: FakeStorageBackend,
) -> None:
    """Verify search filter, rename, move, and deletion lifecycle."""
    token = create_session_token(user_id=str(test_user.id))
    root_id = await fake_storage.ensure_root(test_user)

    # Seed initial items in storage
    subfolder_id = await fake_storage.create_folder(test_user, root_id, "Downloads")
    file_id = f"file_{uuid.uuid4().hex[:8]}"
    fake_storage.files[file_id] = StoredFile(
        id=file_id,
        name="linux-ubuntu.iso",
        parent_id=root_id,
        mime_type="application/x-iso9660-image",
        size_bytes=2_500_000_000,
        md5="d41d8cd98f00b204e9800998ecf8427e",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app_with_library),
        base_url="http://test",
        cookies={"driveseed_session": token},
    ) as client:
        # 1. Search matching "ubuntu"
        res = await client.get("/api/files?search=ubuntu")
        assert res.status_code == 200
        files = res.json()["files"]
        assert len(files) == 1
        assert files[0]["name"] == "linux-ubuntu.iso"

        # 2. Search not matching
        res_empty = await client.get("/api/files?search=windows")
        assert res_empty.status_code == 200
        assert len(res_empty.json()["files"]) == 0

        # 3. Rename file to "ubuntu-24.iso"
        res_rename = await client.patch(f"/api/files/{file_id}", json={"name": "ubuntu-24.iso"})
        assert res_rename.status_code == 200
        assert res_rename.json()["name"] == "ubuntu-24.iso"

        # 4. Move file into "Downloads" subfolder
        res_move = await client.patch(f"/api/files/{file_id}", json={"parent_id": subfolder_id})
        assert res_move.status_code == 200
        assert res_move.json()["parent_id"] == subfolder_id

        # 5. List root folder -> file is moved, only "Downloads" folder in root
        res_root = await client.get("/api/files")
        assert len(res_root.json()["files"]) == 1
        assert res_root.json()["files"][0]["id"] == subfolder_id

        # 6. List subfolder -> file is present inside
        res_sub = await client.get(f"/api/files?folder={subfolder_id}")
        assert len(res_sub.json()["files"]) == 1
        assert res_sub.json()["files"][0]["id"] == file_id

        # 7. Delete file
        res_del = await client.delete(f"/api/files/{file_id}")
        assert res_del.status_code == 204

        # 8. List subfolder after delete -> empty
        res_sub_empty = await client.get(f"/api/files?folder={subfolder_id}")
        assert len(res_sub_empty.json()["files"]) == 0
