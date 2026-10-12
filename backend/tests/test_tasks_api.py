"""Tests for tasks API endpoints, authentication, and lifecycle transitions."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.tasks import get_task_service
from app.core.db import get_db_session
from app.core.security import create_session_token, encrypt_token
from app.main import create_app
from app.models.task import Task
from app.models.user import User
from app.services.storage import StorageService
from app.services.task import TaskService
from tests.fakes.fake_db import FakeAsyncSession
from tests.fakes.fake_storage import FakeStorageBackend


@pytest.fixture
def fake_db() -> FakeAsyncSession:
    """Fixture providing a fresh in-memory database session."""
    return FakeAsyncSession()


@pytest.fixture
def fake_storage() -> FakeStorageBackend:
    """Fixture providing a fake storage backend."""
    return FakeStorageBackend()


@pytest.fixture
def test_user(fake_db: FakeAsyncSession) -> User:
    """Fixture providing an existing authenticated user in the fake db."""
    user = User(
        id=uuid.uuid4(),
        google_sub="sub-test-tasks-user",
        email="tasker@example.com",
        drive_refresh_token_enc=encrypt_token("fake_refresh_token"),
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
def app_with_db(fake_db: FakeAsyncSession, fake_storage: FakeStorageBackend):
    """FastAPI app instance with overridden get_db_session and get_task_service dependencies."""
    app = create_app()

    async def override_get_db() -> AsyncGenerator[FakeAsyncSession, None]:
        yield fake_db

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_task_service] = lambda: TaskService(
        storage_service=StorageService(storage=fake_storage)
    )
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


@pytest.mark.asyncio
async def test_task_start_with_file_selection(
    app_with_db,
    fake_db: FakeAsyncSession,
    test_user: User,
    auth_headers_and_cookies: dict[str, str],
) -> None:
    """Verify starting task with subset of chosen files updates selection and begins download."""
    from app.models.task_file import TaskFile

    task = Task(
        user_id=test_user.id,
        source_type="magnet",
        source_uri="magnet:?xt=urn:btih:fileselect",
        name="multi-file-torrent",
        state="awaiting_selection",
        progress=0.0,
    )
    fake_db.add(task)

    f1 = TaskFile(
        task_id=task.id,
        path="video1.mp4",
        size_bytes=100 * 1024 * 1024,
        selected=True,
        state="pending",
    )
    f2 = TaskFile(
        task_id=task.id,
        path="video2.mp4",
        size_bytes=200 * 1024 * 1024,
        selected=True,
        state="pending",
    )
    fake_db.add(f1)
    fake_db.add(f2)

    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=auth_headers_and_cookies
    ) as client:
        # Start only selecting f1
        res = await client.post(
            f"/api/tasks/{task.id}/start",
            json={"selected_file_ids": [str(f1.id)]},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["state"] == "downloading"

        files = {f["path"]: f["selected"] for f in data["files"]}
        assert files["video1.mp4"] is True
        assert files["video2.mp4"] is False


@pytest.mark.asyncio
async def test_task_start_insufficient_storage_rejected(
    app_with_db,
    fake_db: FakeAsyncSession,
    test_user: User,
    auth_headers_and_cookies: dict[str, str],
) -> None:
    """Verify pre-flight check rejects task start when selected size exceeds Drive space."""
    from app.api.tasks import get_task_service
    from app.interfaces.types import StorageQuota
    from app.models.task_file import TaskFile
    from app.services.storage import StorageService
    from app.services.task import TaskService
    from tests.fakes.fake_storage import FakeStorageBackend

    class TinyStorage(FakeStorageBackend):
        async def quota(self, user: User) -> StorageQuota:
            # 1 MB free space
            return StorageQuota(
                used_bytes=14 * 1024 * 1024 * 1024 + 1023 * 1024 * 1024,
                total_bytes=15 * 1024 * 1024 * 1024,
            )

    custom_task_service = TaskService(storage_service=StorageService(storage=TinyStorage()))
    app_with_db.dependency_overrides[get_task_service] = lambda: custom_task_service

    task = Task(
        user_id=test_user.id,
        source_type="magnet",
        source_uri="magnet:?xt=urn:btih:toobig",
        name="huge-torrent",
        state="awaiting_selection",
    )
    fake_db.add(task)

    huge_file = TaskFile(
        task_id=task.id,
        path="huge_video.mkv",
        size_bytes=10 * 1024 * 1024 * 1024,  # 10 GB
        selected=True,
    )
    fake_db.add(huge_file)

    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=auth_headers_and_cookies
    ) as client:
        res = await client.post(
            f"/api/tasks/{task.id}/start",
            json={"selected_file_ids": [str(huge_file.id)]},
        )
        assert res.status_code == 400
        assert res.json()["detail"]["error"]["code"] == "insufficient_storage"


@pytest.mark.asyncio
async def test_task_retry_lifecycle(
    app_with_db,
    fake_db: FakeAsyncSession,
    test_user: User,
    auth_headers_and_cookies: dict[str, str],
) -> None:
    """Verify retrying a failed task resets error and transitions to queued."""
    failed_task = Task(
        user_id=test_user.id,
        source_type="magnet",
        source_uri="magnet:?xt=urn:btih:retrytest",
        name="failed-torrent.iso",
        state="failed",
        error="Drive quota exceeded during upload",
    )
    fake_db.add(failed_task)

    active_task = Task(
        user_id=test_user.id,
        source_type="url",
        source_uri="https://example.com/file.iso",
        name="file.iso",
        state="downloading",
    )
    fake_db.add(active_task)

    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=auth_headers_and_cookies
    ) as client:
        # 1. Retrying failed task succeeds and resets state to queued
        retry_resp = await client.post(f"/api/tasks/{failed_task.id}/retry")
        assert retry_resp.status_code == 200
        assert retry_resp.json()["state"] == "queued"
        assert failed_task.state == "queued"
        assert failed_task.error is None

        # 2. Retrying an active task fails with 400 invalid_transition
        active_retry_resp = await client.post(f"/api/tasks/{active_task.id}/retry")
        assert active_retry_resp.status_code == 400
        assert active_retry_resp.json()["detail"]["error"]["code"] == "invalid_transition"

        # 3. Retrying non-existent task returns 404
        random_id = uuid.uuid4()
        not_found_resp = await client.post(f"/api/tasks/{random_id}/retry")
        assert not_found_resp.status_code == 404
        assert not_found_resp.json()["detail"]["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_create_task_active_cap_exceeded(
    app_with_db,
    fake_db: FakeAsyncSession,
    test_user: User,
    auth_headers_and_cookies: dict[str, str],
) -> None:
    """Verify POST /api/tasks returns 429 when user has 3 active tasks."""
    for i in range(3):
        fake_db.add(
            Task(
                user_id=test_user.id,
                source_type="url",
                source_uri=f"https://example.com/file{i}.zip",
                name=f"file{i}.zip",
                state="downloading",
            )
        )

    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=auth_headers_and_cookies
    ) as client:
        res = await client.post(
            "/api/tasks",
            json={"source_uri": "https://example.com/exceed.zip"},
        )
        assert res.status_code == 429
        body = res.json()
        assert body["detail"]["error"]["code"] == "task_cap_exceeded"
        assert "3" in body["detail"]["error"]["message"]


@pytest.mark.asyncio
async def test_retry_task_active_cap_exceeded(
    app_with_db,
    fake_db: FakeAsyncSession,
    test_user: User,
    auth_headers_and_cookies: dict[str, str],
) -> None:
    """Verify POST /api/tasks/{id}/retry returns 429 when user already has 3 active tasks."""
    for i in range(3):
        fake_db.add(
            Task(
                user_id=test_user.id,
                source_type="url",
                source_uri=f"https://example.com/file{i}.zip",
                name=f"file{i}.zip",
                state="downloading",
            )
        )
    failed_task = Task(
        user_id=test_user.id,
        source_type="url",
        source_uri="https://example.com/failed.zip",
        name="failed.zip",
        state="failed",
    )
    fake_db.add(failed_task)

    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=auth_headers_and_cookies
    ) as client:
        res = await client.post(f"/api/tasks/{failed_task.id}/retry")
        assert res.status_code == 429
        body = res.json()
        assert body["detail"]["error"]["code"] == "task_cap_exceeded"


@pytest.mark.asyncio
async def test_create_task_rate_limit_exceeded(
    app_with_db,
    auth_headers_and_cookies: dict[str, str],
) -> None:
    """Verify POST /api/tasks returns 429 when rate limit of 10 requests per minute is exceeded."""
    from app.core.rate_limit import get_tasks_rate_limiter

    limiter = get_tasks_rate_limiter()
    limiter.reset()

    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=auth_headers_and_cookies
    ) as client:
        for _ in range(10):
            res = await client.post(
                "/api/tasks",
                json={"source_uri": "https://example.com/file.zip"},
            )
            if res.status_code == 429:
                assert res.json()["detail"]["error"]["code"] == "task_cap_exceeded"

        # 11th request MUST be rate limited
        res11 = await client.post(
            "/api/tasks",
            json={"source_uri": "https://example.com/file.zip"},
        )
        assert res11.status_code == 429
        body = res11.json()
        assert body["detail"]["error"]["code"] == "rate_limit_exceeded"
        assert "Retry-After" in res11.headers

    limiter.reset()
