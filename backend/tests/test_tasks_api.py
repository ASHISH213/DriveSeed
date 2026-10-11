"""Tests for tasks API endpoints, authentication, and lifecycle transitions."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import get_db_session
from app.core.security import create_session_token
from app.main import create_app
from app.models.task import Task
from app.models.user import User
from tests.fakes.fake_db import FakeAsyncSession


@pytest.fixture
def fake_db() -> FakeAsyncSession:
    """Fixture providing a fresh in-memory database session."""
    return FakeAsyncSession()


@pytest.fixture
def test_user(fake_db: FakeAsyncSession) -> User:
    """Fixture providing an existing authenticated user in the fake db."""
    user = User(
        id=uuid.uuid4(),
        google_sub="sub-test-tasks-user",
        email="tasker@example.com",
        drive_refresh_token_enc="fake_encrypted_token",
        drive_root_folder_id="drive-root-folder-123",
        created_at=datetime.now(UTC),
    )
    fake_db.add(user)
    return user


@pytest.fixture
def auth_headers_and_cookies(test_user: User) -> dict[str, str]:
    """Fixture providing session cookie for test_user."""
    token = create_session_token(user_id=str(test_user.id))
    return {"driveseed_session": token}


@pytest.fixture
def app_with_db(fake_db: FakeAsyncSession):
    """FastAPI app instance with overridden get_db_session dependency."""
    app = create_app()

    async def override_get_db() -> AsyncGenerator[FakeAsyncSession, None]:
        yield fake_db

    app.dependency_overrides[get_db_session] = override_get_db
    return app


@pytest.mark.asyncio
async def test_unauthenticated_task_routes_rejected(app_with_db) -> None:
    """Verify all /api/tasks routes reject unauthenticated requests with 401."""
    transport = ASGITransport(app=app_with_db)
    random_id = uuid.uuid4()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /api/tasks
        resp = await client.get("/api/tasks")
        assert resp.status_code == 401
        assert resp.json()["detail"]["error"]["code"] == "unauthorized"

        # POST /api/tasks
        resp = await client.post("/api/tasks", json={"source_uri": "https://example.com/file.zip"})
        assert resp.status_code == 401

        # GET /api/tasks/{id}
        resp = await client.get(f"/api/tasks/{random_id}")
        assert resp.status_code == 401

        # POST /api/tasks/{id}/pause
        resp = await client.post(f"/api/tasks/{random_id}/pause")
        assert resp.status_code == 401

        # POST /api/tasks/{id}/resume
        resp = await client.post(f"/api/tasks/{random_id}/resume")
        assert resp.status_code == 401

        # POST /api/tasks/{id}/cancel
        resp = await client.post(f"/api/tasks/{random_id}/cancel")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_magnet_task(
    app_with_db, test_user: User, auth_headers_and_cookies: dict[str, str]
) -> None:
    """Verify creating a task with a magnet link parses info_hash and dn name."""
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=auth_headers_and_cookies
    ) as client:
        magnet_uri = (
            "magnet:?xt=urn:btih:da39a3ee5e6b4b0d3255bfef95601890afd80709"
            "&dn=Ubuntu-24.04-desktop.iso&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80"
        )
        resp = await client.post("/api/tasks", json={"source_uri": magnet_uri})
        assert resp.status_code == 201

        data = resp.json()
        assert data["source_type"] == "magnet"
        assert data["info_hash"] == "da39a3ee5e6b4b0d3255bfef95601890afd80709"
        assert data["name"] == "Ubuntu-24.04-desktop.iso"
        assert data["state"] == "queued"
        assert data["progress"] == 0.0
        assert data["user_id"] == str(test_user.id)
        assert data["files"] == []


@pytest.mark.asyncio
async def test_create_direct_url_task(
    app_with_db, test_user: User, auth_headers_and_cookies: dict[str, str]
) -> None:
    """Verify creating a task with a direct HTTP URL parses filename from path."""
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=auth_headers_and_cookies
    ) as client:
        resp = await client.post(
            "/api/tasks",
            json={
                "source_uri": "https://example.com/downloads/archive.tar.gz",
                "name": "Custom Archive Name",
            },
        )
        assert resp.status_code == 201

        data = resp.json()
        assert data["source_type"] == "url"
        assert data["info_hash"] is None
        assert data["name"] == "Custom Archive Name"
        assert data["state"] == "queued"
        assert data["user_id"] == str(test_user.id)


@pytest.mark.asyncio
async def test_create_task_invalid_source_rejected(
    app_with_db, auth_headers_and_cookies: dict[str, str]
) -> None:
    """Verify creating a task with invalid protocol returns 400 bad request."""
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=auth_headers_and_cookies
    ) as client:
        resp = await client.post(
            "/api/tasks",
            json={"source_uri": "ftp://files.example.com/unsupported.iso"},
        )
        assert resp.status_code == 400
        error = resp.json()["detail"]["error"]
        assert error["code"] == "invalid_input"
        assert "Invalid source URI" in error["message"]


@pytest.mark.asyncio
async def test_list_and_get_tasks_with_user_isolation(
    app_with_db,
    fake_db: FakeAsyncSession,
    test_user: User,
    auth_headers_and_cookies: dict[str, str],
) -> None:
    """Verify listing tasks returns user's tasks and isolates other users' tasks."""
    other_user = User(
        id=uuid.uuid4(),
        google_sub="other-sub",
        email="other@example.com",
    )
    fake_db.add(other_user)

    # Task for other user
    other_task = Task(
        user_id=other_user.id,
        source_type="url",
        source_uri="https://other.com/secret.pdf",
        name="secret.pdf",
        state="queued",
    )
    fake_db.add(other_task)

    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=auth_headers_and_cookies
    ) as client:
        # Initially 0 tasks for test_user
        list_resp = await client.get("/api/tasks")
        assert list_resp.status_code == 200
        assert list_resp.json() == []

        # Create task for test_user
        post_resp = await client.post(
            "/api/tasks",
            json={"source_uri": "https://example.com/doc1.pdf"},
        )
        created_id = post_resp.json()["id"]

        # List should now return 1 task
        list_resp2 = await client.get("/api/tasks")
        assert list_resp2.status_code == 200
        items = list_resp2.json()
        assert len(items) == 1
        assert items[0]["id"] == created_id

        # Get specific task
        get_resp = await client.get(f"/api/tasks/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == created_id

        # Trying to get other user's task returns 404
        get_other_resp = await client.get(f"/api/tasks/{other_task.id}")
        assert get_other_resp.status_code == 404
        assert get_other_resp.json()["detail"]["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_task_lifecycle_transitions(
    app_with_db,
    fake_db: FakeAsyncSession,
    test_user: User,
    auth_headers_and_cookies: dict[str, str],
) -> None:
    """Verify state transitions pause -> resume -> cancel and rejection of forbidden transitions."""
    # Seed task in downloading state
    task = Task(
        user_id=test_user.id,
        source_type="magnet",
        source_uri="magnet:?xt=urn:btih:abc",
        name="linux.iso",
        state="downloading",
    )
    fake_db.add(task)

    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=auth_headers_and_cookies
    ) as client:
        # 1. Pause active downloading task -> paused
        pause_resp = await client.post(f"/api/tasks/{task.id}/pause")
        assert pause_resp.status_code == 200
        assert pause_resp.json()["state"] == "paused"

        # 2. Cannot pause an already paused task -> 400 invalid_transition
        pause_again_resp = await client.post(f"/api/tasks/{task.id}/pause")
        assert pause_again_resp.status_code == 400
        assert pause_again_resp.json()["detail"]["error"]["code"] == "invalid_transition"

        # 3. Resume paused task -> downloading
        resume_resp = await client.post(f"/api/tasks/{task.id}/resume")
        assert resume_resp.status_code == 200
        assert resume_resp.json()["state"] == "downloading"

        # 4. Cancel active task -> cancelled
        cancel_resp = await client.post(f"/api/tasks/{task.id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["state"] == "cancelled"

        # 5. Cannot resume or pause a cancelled task -> 400 invalid_transition
        resume_cancelled_resp = await client.post(f"/api/tasks/{task.id}/resume")
        assert resume_cancelled_resp.status_code == 400
        assert resume_cancelled_resp.json()["detail"]["error"]["code"] == "invalid_transition"
