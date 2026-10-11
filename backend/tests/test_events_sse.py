"""Tests for live Server-Sent Events (SSE) progress endpoint and Redis pub/sub broadcasting."""

import contextlib
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import get_db_session
from app.core.security import create_session_token, encrypt_token
from app.main import create_app
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreateRequest
from app.services.events import (
    EventBroadcaster,
    TaskEvent,
    get_event_broadcaster,
    set_event_broadcaster,
)
from app.services.task import TaskService
from app.workers.pipeline import process_download_task
from tests.fakes.fake_db import FakeAsyncSession
from tests.fakes.fake_download import FakeDownloadEngine
from tests.fakes.fake_redis import FakeRedis
from tests.fakes.fake_storage import FakeStorageBackend


@pytest.fixture
def fake_db() -> FakeAsyncSession:
    """Fixture providing in-memory database session."""
    return FakeAsyncSession()


@pytest.fixture
def fake_redis() -> FakeRedis:
    """Fixture providing in-memory fake Redis client."""
    return FakeRedis()


@pytest.fixture
def test_broadcaster(fake_redis: FakeRedis) -> EventBroadcaster:
    """Fixture providing EventBroadcaster backed by fake Redis."""
    broadcaster = EventBroadcaster(redis_client=fake_redis)
    set_event_broadcaster(broadcaster)
    yield broadcaster
    set_event_broadcaster(None)


@pytest.fixture
def test_user(fake_db: FakeAsyncSession) -> User:
    """Fixture providing an existing authenticated user."""
    user = User(
        id=uuid.uuid4(),
        google_sub="sub-test-sse-user",
        email="streamer@example.com",
        drive_refresh_token_enc=encrypt_token("mock-refresh-token"),
        drive_root_folder_id="drive-root-folder-123",
        created_at=datetime.now(UTC),
    )
    fake_db.add(user)
    return user


@pytest.fixture
def app_with_db(
    fake_db: FakeAsyncSession,
    test_broadcaster: EventBroadcaster,
):
    """FastAPI application with dependency overrides."""
    app = create_app()

    async def override_get_db() -> AsyncGenerator[FakeAsyncSession, None]:
        yield fake_db

    def override_broadcaster() -> EventBroadcaster:
        return test_broadcaster

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_event_broadcaster] = override_broadcaster
    return app


@pytest.mark.asyncio
async def test_unauthenticated_events_endpoints_rejected(app_with_db) -> None:
    """Verify unauthenticated requests to /events and /api/events return 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_db),
        base_url="http://test",
    ) as client:
        res1 = await client.get("/events")
        assert res1.status_code == 401
        assert res1.json()["detail"]["error"]["code"] == "unauthorized"

        res2 = await client.get("/api/events")
        assert res2.status_code == 401
        assert res2.json()["detail"]["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_events_stream_connects_with_cookie(
    app_with_db,
    test_user: User,
) -> None:
    """Verify authenticated SSE stream connects with session cookie."""
    token = create_session_token(user_id=str(test_user.id))

    async with AsyncClient(
        transport=ASGITransport(app=app_with_db),
        base_url="http://test",
        cookies={"driveseed_session": token},
    ) as client:
        res = await client.get("/events?limit=1")
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        assert res.headers.get("x-accel-buffering") == "no"
        assert ": connected" in res.text


@pytest.mark.asyncio
async def test_events_stream_connects_with_bearer_token(
    app_with_db,
    test_user: User,
) -> None:
    """Verify authenticated SSE stream connects with Authorization Bearer header."""
    token = create_session_token(user_id=str(test_user.id))

    async with AsyncClient(
        transport=ASGITransport(app=app_with_db),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        res = await client.get("/events?limit=1")
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        assert ": connected" in res.text


@pytest.mark.asyncio
async def test_events_stream_connects_with_query_param(
    app_with_db,
    test_user: User,
) -> None:
    """Verify curl-style query parameter authentication (?token=...) works."""
    token = create_session_token(user_id=str(test_user.id))

    async with AsyncClient(
        transport=ASGITransport(app=app_with_db),
        base_url="http://test",
    ) as client:
        res = await client.get(f"/events?token={token}&limit=1")
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        assert ": connected" in res.text


@pytest.mark.asyncio
async def test_events_live_task_progress_broadcast(
    test_user: User,
    test_broadcaster: EventBroadcaster,
) -> None:
    """Verify published TaskEvents are streamed to the subscribed client."""
    gen = test_broadcaster.subscribe(user_id=str(test_user.id))
    try:
        # Step 1: verify initial connection comment
        initial_chunk = await anext(gen)
        assert initial_chunk == ": connected\n\n"

        # Step 2: publish progress event
        task_id = str(uuid.uuid4())
        event = TaskEvent(
            task_id=task_id,
            user_id=str(test_user.id),
            name="ubuntu-24.04.iso",
            state="downloading",
            progress=0.45,
            speed_bps=2_500_000.0,
            downloaded_bytes=450_000_000,
            total_bytes=1_000_000_000,
        )
        await test_broadcaster.publish(event)

        # Step 3: verify incoming SSE event chunk
        msg_chunk = await anext(gen)
        assert msg_chunk.startswith("event: task_update\ndata: ")
        data_str = msg_chunk.replace("event: task_update\ndata: ", "").rstrip("\n")
        payload = json.loads(data_str)
        assert payload["task_id"] == task_id
        assert payload["user_id"] == str(test_user.id)
        assert payload["state"] == "downloading"
        assert payload["progress"] == 0.45
        assert payload["speed_bps"] == 2_500_000.0
        assert payload["downloaded_bytes"] == 450_000_000
        assert payload["total_bytes"] == 1_000_000_000
        assert payload["name"] == "ubuntu-24.04.iso"
    finally:
        await gen.aclose()


@pytest.mark.asyncio
async def test_events_multi_user_isolation(
    test_user: User,
    test_broadcaster: EventBroadcaster,
) -> None:
    """Verify user only receives events directed to their own user_id."""
    gen = test_broadcaster.subscribe(user_id=str(test_user.id))
    try:
        assert await anext(gen) == ": connected\n\n"

        # Publish event for a DIFFERENT user
        other_user_id = str(uuid.uuid4())
        other_event = TaskEvent(
            task_id=str(uuid.uuid4()),
            user_id=other_user_id,
            name="secret.zip",
            state="downloading",
            progress=0.1,
        )
        await test_broadcaster.publish(other_event)

        # Publish event for current user
        my_task_id = str(uuid.uuid4())
        my_event = TaskEvent(
            task_id=my_task_id,
            user_id=str(test_user.id),
            name="my-file.tar.gz",
            state="downloading",
            progress=0.8,
        )
        await test_broadcaster.publish(my_event)

        # Client receives current user's event, never the other user's event
        msg_chunk = await anext(gen)
        data_str = msg_chunk.replace("event: task_update\ndata: ", "").rstrip("\n")
        payload = json.loads(data_str)
        assert payload["task_id"] == my_task_id
        assert payload["name"] == "my-file.tar.gz"
    finally:
        await gen.aclose()


@pytest.mark.asyncio
async def test_events_heartbeat_ping(
    test_user: User,
    test_broadcaster: EventBroadcaster,
) -> None:
    """Verify idle subscribers receive heartbeat pings (: ping\\n\\n)."""
    gen = test_broadcaster.subscribe(user_id=str(test_user.id), heartbeat_interval=0.01)
    try:
        assert await anext(gen) == ": connected\n\n"
        ping_chunk = await anext(gen)
        assert ping_chunk == ": ping\n\n"
    finally:
        await gen.aclose()


@pytest.mark.asyncio
async def test_events_client_disconnect_unsubscribes(
    test_user: User,
    test_broadcaster: EventBroadcaster,
    fake_redis: FakeRedis,
) -> None:
    """Verify closing the generator cleanly unsubscribes without leaking Redis channels."""
    user_id = str(test_user.id)
    channel = test_broadcaster.get_channel(user_id)
    gen = test_broadcaster.subscribe(user_id=user_id)

    assert await anext(gen) == ": connected\n\n"
    assert len(fake_redis.subscribers.get(channel, [])) == 1

    # Simulate client disconnect / generator closure
    await gen.aclose()
    assert len(fake_redis.subscribers.get(channel, [])) == 0


@pytest.mark.asyncio
async def test_task_service_lifecycle_emits_events(
    fake_db: FakeAsyncSession,
    test_user: User,
    fake_redis: FakeRedis,
    test_broadcaster: EventBroadcaster,
) -> None:
    """Verify TaskService mutations publish real-time events."""
    service = TaskService(queue=None, broadcaster=test_broadcaster)

    # 1. Create task -> event emitted
    task = await service.create_task(
        db=fake_db,
        user=test_user,
        request=TaskCreateRequest(
            source_uri="https://example.com/movie.mp4",
            name="My Movie",
        ),
    )
    assert len(fake_redis.published_messages) >= 1
    last_channel, last_msg = fake_redis.published_messages[-1]
    assert last_channel == f"driveseed:events:{test_user.id}"
    msg_data = json.loads(last_msg)
    assert msg_data["task_id"] == str(task.id)
    assert msg_data["state"] == "queued"

    # 2. Transition to downloading manually to allow pause
    task.state = "downloading"
    await fake_db.commit()

    # 3. Pause task -> event emitted
    await service.pause_task(db=fake_db, user=test_user, task_id=task.id)
    msg_data = json.loads(fake_redis.published_messages[-1][1])
    assert msg_data["state"] == "paused"

    # 4. Resume task -> event emitted
    await service.resume_task(db=fake_db, user=test_user, task_id=task.id)
    msg_data = json.loads(fake_redis.published_messages[-1][1])
    assert msg_data["state"] == "downloading"

    # 5. Cancel task -> event emitted
    await service.cancel_task(db=fake_db, user=test_user, task_id=task.id)
    msg_data = json.loads(fake_redis.published_messages[-1][1])
    assert msg_data["state"] == "cancelled"


@pytest.mark.asyncio
async def test_worker_pipeline_emits_events(
    fake_db: FakeAsyncSession,
    test_user: User,
    fake_redis: FakeRedis,
    test_broadcaster: EventBroadcaster,
) -> None:
    """Verify worker pipeline emits progress and state events into Redis pub/sub."""
    task_id = uuid.uuid4()
    task = Task(
        id=task_id,
        user_id=test_user.id,
        source_type="url",
        source_uri="https://example.com/test.bin",
        name="test.bin",
        state="queued",
        progress=0.0,
        size_bytes=1000,
    )
    fake_db.add(task)

    engine = FakeDownloadEngine()
    storage = FakeStorageBackend()

    @contextlib.asynccontextmanager
    async def fake_session_factory() -> AsyncGenerator[FakeAsyncSession, None]:
        yield fake_db

    ctx = {
        "db_session_factory": fake_session_factory,
        "download_engine": engine,
        "storage_backend": storage,
        "event_broadcaster": test_broadcaster,
    }

    await process_download_task(ctx=ctx, task_id=str(task_id))

    # Inspect all published events
    events = [
        json.loads(msg)
        for ch, msg in fake_redis.published_messages
        if ch == f"driveseed:events:{test_user.id}"
    ]
    states = [e["state"] for e in events]

    assert "downloading" in states
    assert "uploading" in states
    assert "completed" in states
