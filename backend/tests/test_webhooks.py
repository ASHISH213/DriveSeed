"""Tests for webhook endpoints, HMAC signatures, lifecycle dispatching, and retries."""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import get_current_user
from app.core.config import Settings
from app.core.db import get_db_session
from app.main import create_app
from app.models.task import Task
from app.models.user import User
from app.services.webhook import WebhookService
from tests.fakes.fake_db import FakeAsyncSession


@pytest.fixture
def fake_db() -> FakeAsyncSession:
    return FakeAsyncSession()


@pytest.fixture
def test_user(fake_db: FakeAsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        google_sub="sub-webhook-test",
        email="webhook@example.com",
        created_at=datetime.now(UTC),
    )
    fake_db.add(user)
    return user


@pytest.mark.asyncio
async def test_webhook_hmac_signature() -> None:
    """Ensure HMAC-SHA256 signature is strictly computed and verifiable."""
    service = WebhookService()
    secret = "whsec_supersecretkey12345"
    payload = b'{"event":"task.completed","task":{"id":"123"}}'

    computed_sig = service.compute_signature(secret, payload)
    expected_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    assert computed_sig == expected_sig
    assert len(computed_sig) == 64


@pytest.mark.asyncio
async def test_webhook_crud_api(fake_db: FakeAsyncSession, test_user: User) -> None:
    """Test POST, GET, and DELETE /api/webhooks."""
    app = create_app(Settings(DEBUG=True))
    app.dependency_overrides[get_db_session] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: test_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Create webhook endpoint
        create_resp = await client.post(
            "/api/webhooks",
            json={
                "url": "https://example.com/webhook",
                "events": ["task.completed", "task.failed"],
            },
        )
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert data["url"] == "https://example.com/webhook"
        assert data["secret"].startswith("whsec_")
        assert "task.completed" in data["events"]
        endpoint_id = data["id"]

        # List endpoints
        list_resp = await client.get("/api/webhooks")
        assert list_resp.status_code == 200
        endpoints = list_resp.json()
        assert len(endpoints) == 1
        assert endpoints[0]["id"] == endpoint_id

        # Delete endpoint
        del_resp = await client.delete(f"/api/webhooks/{endpoint_id}")
        assert del_resp.status_code == 204

        # List again -> empty
        list_resp2 = await client.get("/api/webhooks")
        assert list_resp2.status_code == 200
        assert len(list_resp2.json()) == 0

        # Delete non-existent -> 404
        del_404 = await client.delete(f"/api/webhooks/{endpoint_id}")
        assert del_404.status_code == 404


@pytest.mark.asyncio
async def test_webhook_invalid_url_rejected(fake_db: FakeAsyncSession, test_user: User) -> None:
    """Ensure invalid schemes are rejected."""
    app = create_app(Settings(DEBUG=True))
    app.dependency_overrides[get_db_session] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: test_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/webhooks",
            json={"url": "ftp://bad-scheme.com/hook"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_webhook_test_ping(fake_db: FakeAsyncSession, test_user: User) -> None:
    """Test POST /api/webhooks/{id}/test endpoint delivers ping with signature."""
    service = WebhookService()
    endpoint = await service.create_endpoint(
        db=fake_db,
        user_id=test_user.id,
        url="https://webhook.site/test-ping",
        allow_local=True,
    )

    received_headers: dict[str, str] = {}
    received_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal received_headers, received_body
        received_headers = dict(request.headers)
        received_body = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    mock_client = httpx.AsyncClient(transport=transport)

    success, status_code, msg = await service.send_test_ping(endpoint, client=mock_client)
    assert success is True
    assert status_code == 200
    assert "sha256=" in received_headers["x-driveseed-signature"]
    assert received_headers["x-driveseed-event"] == "ping"
    assert received_body["event"] == "ping"
    assert received_body["endpoint_id"] == str(endpoint.id)


@pytest.mark.asyncio
async def test_webhook_dispatch_on_task_completed(
    fake_db: FakeAsyncSession, test_user: User
) -> None:
    """Verify task.completed delivers signed payload with task details."""
    service = WebhookService()
    _endpoint = await service.create_endpoint(
        db=fake_db,
        user_id=test_user.id,
        url="https://receiver.example.com/hook",
        events=["task.completed"],
        allow_local=True,
    )

    task = Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Ubuntu 24.04 ISO",
        source_type="torrent",
        source_uri="magnet:?xt=urn:btih:dummy",
        state="completed",
        size_bytes=4294967296,
        progress=1.0,
        completed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    fake_db.add(task)

    dispatched_requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        dispatched_requests.append(
            {
                "headers": dict(request.headers),
                "body": body,
            }
        )
        return httpx.Response(200, text="Acknowledged")

    transport = httpx.MockTransport(handler)
    mock_client = httpx.AsyncClient(transport=transport)

    count = await service.dispatch_task_event(
        db=fake_db,
        user_id=test_user.id,
        event_name="task.completed",
        task=task,
        client=mock_client,
    )

    assert count == 1
    assert len(dispatched_requests) == 1
    req = dispatched_requests[0]
    assert req["body"]["event"] == "task.completed"
    assert req["body"]["task"]["name"] == "Ubuntu 24.04 ISO"
    assert req["body"]["task"]["state"] == "completed"
    assert req["headers"]["x-driveseed-signature"].startswith("sha256=")


@pytest.mark.asyncio
async def test_webhook_delivery_retries() -> None:
    """Verify retry logic on transient HTTP 5xx errors."""
    service = WebhookService()
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(502, text="Bad Gateway")
        return httpx.Response(200, text="Success on attempt 3")

    transport = httpx.MockTransport(handler)
    mock_client = httpx.AsyncClient(transport=transport)

    success, status_code, message = await service.deliver_payload(
        url="https://flaky-server.example.com/hook",
        secret="whsec_12345",
        event_name="task.completed",
        payload_data={"task_id": "xyz"},
        max_retries=3,
        client=mock_client,
    )

    assert attempts == 3
    assert success is True
    assert status_code == 200
    assert "Success on attempt 3" in message
