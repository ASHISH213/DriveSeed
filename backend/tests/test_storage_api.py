"""Tests for Storage API endpoint: Drive quota metrics and error handling."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import get_auth_service
from app.api.storage import get_storage_service
from app.core.config import Settings
from app.core.db import get_db_session
from app.core.security import create_session_token, encrypt_token
from app.interfaces.types import StorageQuota
from app.main import create_app
from app.models.user import User
from app.services.auth import AuthService
from app.services.storage import StorageService
from tests.fakes.fake_db import FakeAsyncSession
from tests.fakes.fake_storage import FakeStorageBackend


@pytest.fixture
def fake_db() -> FakeAsyncSession:
    """Fixture providing in-memory fake database session."""
    return FakeAsyncSession()


@pytest.fixture
def fake_storage() -> FakeStorageBackend:
    """Fixture providing in-memory fake storage backend."""
    return FakeStorageBackend()


@pytest.fixture
def test_user(fake_db: FakeAsyncSession) -> User:
    """Fixture providing an authenticated user with connected Google Drive."""
    user = User(
        id=uuid.uuid4(),
        google_sub="sub-storage-user",
        email="storage@example.com",
        drive_refresh_token_enc=encrypt_token("mock-refresh-token"),
        drive_root_folder_id=None,
        created_at=datetime.now(UTC),
    )
    fake_db.add(user)
    return user


@pytest.fixture
def disconnected_user(fake_db: FakeAsyncSession) -> User:
    """Fixture providing a user without connected Google Drive account."""
    user = User(
        id=uuid.uuid4(),
        google_sub="sub-no-drive-user",
        email="nodrive@example.com",
        drive_refresh_token_enc=None,
        drive_root_folder_id=None,
        created_at=datetime.now(UTC),
    )
    fake_db.add(user)
    return user


class FakeAuthService(AuthService):
    """Auth service fake returning users from test setup."""

    def __init__(self, users: dict[str, User]) -> None:
        super().__init__(settings=Settings())
        self._token_to_user = users

    async def get_current_user(self, db, session_token: str | None) -> User | None:
        if not session_token:
            return None
        return self._token_to_user.get(session_token)


@pytest.fixture
def app_with_storage(
    fake_db: FakeAsyncSession,
    fake_storage: FakeStorageBackend,
    test_user: User,
    disconnected_user: User,
):
    """FastAPI application configured with storage service and auth fakes."""
    app = create_app()

    connected_token = create_session_token(str(test_user.id))
    disconnected_token = create_session_token(str(disconnected_user.id))

    auth_fake = FakeAuthService(
        users={
            connected_token: test_user,
            disconnected_token: disconnected_user,
        }
    )

    async def override_get_db() -> AsyncGenerator[FakeAsyncSession, None]:
        yield fake_db

    storage_service = StorageService(storage=fake_storage)

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_auth_service] = lambda: auth_fake
    app.dependency_overrides[get_storage_service] = lambda: storage_service

    return app, connected_token, disconnected_token, fake_storage


@pytest.mark.asyncio
async def test_get_storage_quota_success(app_with_storage):
    """GET /api/storage returns calculated metrics for connected user."""
    app, token, _, fake_storage = app_with_storage

    # Store 3 GB of simulated data
    fake_storage.file_data["f1"] = b"x" * (3 * 1024 * 1024 * 1024)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"driveseed_session": token},
    ) as client:
        res = await client.get("/api/storage")
        assert res.status_code == 200
        data = res.json()

        assert data["used_bytes"] == 3 * 1024 * 1024 * 1024
        assert data["total_bytes"] == 15 * 1024 * 1024 * 1024
        assert data["free_bytes"] == 12 * 1024 * 1024 * 1024
        assert data["percent_used"] == 20.0


@pytest.mark.asyncio
async def test_get_storage_quota_full_drive(app_with_storage):
    """GET /api/storage correctly calculates 100% capacity when drive is full."""
    app, token, _, fake_storage = app_with_storage

    class FullStorageBackend(FakeStorageBackend):
        async def quota(self, user: User) -> StorageQuota:
            return StorageQuota(
                used_bytes=15 * 1024 * 1024 * 1024,
                total_bytes=15 * 1024 * 1024 * 1024,
            )

    app.dependency_overrides[get_storage_service] = lambda: StorageService(
        storage=FullStorageBackend()
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"driveseed_session": token},
    ) as client:
        res = await client.get("/api/storage")
        assert res.status_code == 200
        data = res.json()

        assert data["used_bytes"] == 15 * 1024 * 1024 * 1024
        assert data["free_bytes"] == 0
        assert data["percent_used"] == 100.0


@pytest.mark.asyncio
async def test_get_storage_quota_requires_auth(app_with_storage):
    """GET /api/storage returns 401 for unauthenticated requests."""
    app, _, _, _ = app_with_storage

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        res = await client.get("/api/storage")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_storage_quota_disconnected_drive(app_with_storage):
    """GET /api/storage returns 400 when Google Drive is not connected."""
    app, _, disconnected_token, _ = app_with_storage

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"driveseed_session": disconnected_token},
    ) as client:
        res = await client.get("/api/storage")
        assert res.status_code == 400
        data = res.json()
        assert data["detail"]["error"]["code"] == "drive_not_connected"
