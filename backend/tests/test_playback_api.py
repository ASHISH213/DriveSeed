"""Tests for Playback API: resume position retrieval, persistence, and isolation."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import get_auth_service
from app.core.config import Settings
from app.core.db import get_db_session
from app.core.security import create_session_token
from app.main import create_app
from app.models.user import User
from app.services.auth import AuthService
from tests.fakes.fake_db import FakeAsyncSession


@pytest.fixture
def fake_db() -> FakeAsyncSession:
    """Fixture providing in-memory fake database session."""
    return FakeAsyncSession()


@pytest.fixture
def test_user(fake_db: FakeAsyncSession) -> User:
    """Fixture providing an authenticated primary test user."""
    user = User(
        id=uuid.uuid4(),
        google_sub="sub-playback-user-1",
        email="playback1@example.com",
        drive_refresh_token_enc=None,
        drive_root_folder_id=None,
        created_at=datetime.now(UTC),
    )
    fake_db.add(user)
    return user


@pytest.fixture
def other_user(fake_db: FakeAsyncSession) -> User:
    """Fixture providing a second authenticated user for isolation testing."""
    user = User(
        id=uuid.uuid4(),
        google_sub="sub-playback-user-2",
        email="playback2@example.com",
        drive_refresh_token_enc=None,
        drive_root_folder_id=None,
        created_at=datetime.now(UTC),
    )
    fake_db.add(user)
    return user


class FakeAuthService(AuthService):
    """Auth service fake returning users from FakeAsyncSession."""

    def __init__(self, users: dict[str, User]) -> None:
        super().__init__(settings=Settings())
        self._token_to_user = users

    async def get_current_user(self, db, session_token: str | None) -> User | None:
        if not session_token:
            return None
        return self._token_to_user.get(session_token)


@pytest.fixture
def app_with_playback(
    fake_db: FakeAsyncSession,
    test_user: User,
    other_user: User,
):
    """FastAPI application configured with test overrides."""
    app = create_app()

    token1 = create_session_token(str(test_user.id))
    token2 = create_session_token(str(other_user.id))

    auth_fake = FakeAuthService(
        users={
            token1: test_user,
            token2: other_user,
        }
    )

    async def override_get_db() -> AsyncGenerator[FakeAsyncSession, None]:
        yield fake_db

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_auth_service] = lambda: auth_fake
    return app, token1, token2


@pytest.mark.asyncio
async def test_get_playback_defaults_to_zero(app_with_playback):
    """Getting playback position for a new file returns 0.0 seconds."""
    app, token, _ = app_with_playback
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"driveseed_session": token},
    ) as client:
        res = await client.get("/api/playback/file_abc123")
        assert res.status_code == 200
        data = res.json()
        assert data["file_id"] == "file_abc123"
        assert data["position_seconds"] == 0.0
        assert data["updated_at"] is None


@pytest.mark.asyncio
async def test_update_and_get_playback_position(app_with_playback):
    """Saving playback position persists and can be retrieved."""
    app, token, _ = app_with_playback
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"driveseed_session": token},
    ) as client:
        # Save position at 145.5 seconds
        put_res = await client.put(
            "/api/playback/file_abc123",
            json={"position_seconds": 145.5},
        )
        assert put_res.status_code == 200
        put_data = put_res.json()
        assert put_data["file_id"] == "file_abc123"
        assert put_data["position_seconds"] == 145.5
        assert put_data["updated_at"] is not None

        # Verify subsequent GET returns the saved position
        get_res = await client.get("/api/playback/file_abc123")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["file_id"] == "file_abc123"
        assert get_data["position_seconds"] == 145.5

        # Update position further to 320.0 seconds
        update_res = await client.put(
            "/api/playback/file_abc123",
            json={"position_seconds": 320.0},
        )
        assert update_res.status_code == 200
        assert update_res.json()["position_seconds"] == 320.0


@pytest.mark.asyncio
async def test_delete_playback_resets_position(app_with_playback):
    """Deleting playback position resets progress back to 0.0."""
    app, token, _ = app_with_playback
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"driveseed_session": token},
    ) as client:
        # Save position
        await client.put(
            "/api/playback/file_delete_test",
            json={"position_seconds": 88.0},
        )

        # Delete position
        del_res = await client.delete("/api/playback/file_delete_test")
        assert del_res.status_code == 204

        # Verify next GET returns 0.0
        get_res = await client.get("/api/playback/file_delete_test")
        assert get_res.status_code == 200
        assert get_res.json()["position_seconds"] == 0.0


@pytest.mark.asyncio
async def test_playback_validation_negative_position(app_with_playback):
    """Negative playback position is rejected with 422."""
    app, token, _ = app_with_playback
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"driveseed_session": token},
    ) as client:
        res = await client.put(
            "/api/playback/file_neg",
            json={"position_seconds": -5.0},
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_playback_requires_authentication(app_with_playback):
    """Unauthenticated requests are rejected with 401."""
    app, _, _ = app_with_playback
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        get_res = await client.get("/api/playback/file_secret")
        assert get_res.status_code == 401

        put_res = await client.put(
            "/api/playback/file_secret",
            json={"position_seconds": 12.0},
        )
        assert put_res.status_code == 401


@pytest.mark.asyncio
async def test_playback_user_isolation(app_with_playback):
    """Playback position for user 1 does not affect user 2."""
    app, token1, token2 = app_with_playback

    async with (
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={"driveseed_session": token1},
        ) as client1,
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={"driveseed_session": token2},
        ) as client2,
    ):
        # User 1 watches file to 500s
        await client1.put(
            "/api/playback/shared_movie",
            json={"position_seconds": 500.0},
        )

        # User 2 checks same file; should still be 0.0
        res_u2 = await client2.get("/api/playback/shared_movie")
        assert res_u2.status_code == 200
        assert res_u2.json()["position_seconds"] == 0.0

        # User 2 watches to 25s
        await client2.put(
            "/api/playback/shared_movie",
            json={"position_seconds": 25.0},
        )

        # User 1 still has 500s
        res_u1 = await client1.get("/api/playback/shared_movie")
        assert res_u1.status_code == 200
        assert res_u1.json()["position_seconds"] == 500.0
