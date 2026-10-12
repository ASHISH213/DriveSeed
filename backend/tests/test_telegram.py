"""Tests for Telegram Bot integration: linking, commands, SSRF, notifications, and webhooks."""

import uuid
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import get_current_user
from app.core.config import Settings
from app.core.db import get_db_session
from app.main import create_app
from app.models.task import Task
from app.models.user import User
from app.services.library import LibraryService
from app.services.task import TaskService
from app.services.telegram import TelegramBotService
from tests.fakes.fake_db import FakeAsyncSession


@pytest.fixture
def fake_db() -> FakeAsyncSession:
    """Fixture providing in-memory fake database session."""
    return FakeAsyncSession()


@pytest.fixture
def test_user() -> User:
    """Fixture providing a test user."""
    return User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        google_sub="google-sub-tg-123",
        telegram_chat_id=None,
    )


@pytest.mark.asyncio
async def test_telegram_link_flow_and_unlink(fake_db: FakeAsyncSession, test_user: User) -> None:
    """Test generating a link token, linking via /start <code>, and unlinking."""
    fake_db.users[test_user.id] = test_user
    service = TelegramBotService(Settings(TELEGRAM_BOT_USERNAME="DriveSeedTestBot"))
    task_service = TaskService()

    # Generate token
    token, deep_link = await service.generate_link_token(fake_db, test_user.id)
    assert len(token) == 6
    assert deep_link == f"https://t.me/DriveSeedTestBot?start={token}"
    assert test_user.telegram_link_token == token

    # Attempt link with invalid token
    update_invalid = {
        "update_id": 1,
        "message": {"chat": {"id": 987654321}, "text": "/start WRONG1"},
    }
    reply = await service.handle_update(fake_db, update_invalid, task_service=task_service)
    assert reply is not None
    assert "Invalid link code" in reply
    assert test_user.telegram_chat_id is None

    # Link with valid token
    update_valid = {
        "update_id": 2,
        "message": {"chat": {"id": 987654321}, "text": f"/start {token}"},
    }
    reply = await service.handle_update(fake_db, update_valid, task_service=task_service)
    assert reply is not None
    assert "Account Linked!" in reply
    assert "testuser@example.com" in reply
    assert test_user.telegram_chat_id == "987654321"
    assert test_user.telegram_link_token is None

    # Verify /start when already linked shows welcome back
    update_start_linked = {
        "update_id": 3,
        "message": {"chat": {"id": 987654321}, "text": "/start"},
    }
    reply_linked = await service.handle_update(
        fake_db, update_start_linked, task_service=task_service
    )
    assert reply_linked is not None
    assert "Welcome back" in reply_linked

    # Unlink account
    update_unlink = {
        "update_id": 4,
        "message": {"chat": {"id": 987654321}, "text": "/unlink"},
    }
    reply_unlink = await service.handle_update(fake_db, update_unlink, task_service=task_service)
    assert reply_unlink is not None
    assert "Account Unlinked" in reply_unlink
    assert test_user.telegram_chat_id is None


@pytest.mark.asyncio
async def test_telegram_add_magnet_and_url(fake_db: FakeAsyncSession, test_user: User) -> None:
    """Test adding magnet link and URL downloads via Telegram."""
    test_user.telegram_chat_id = "11223344"
    fake_db.users[test_user.id] = test_user
    service = TelegramBotService(Settings(DEBUG=True))
    task_service = TaskService()

    # Raw magnet paste
    magnet = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=Ubuntu.iso"
    update_magnet = {
        "update_id": 10,
        "message": {"chat": {"id": 11223344}, "text": magnet},
    }
    reply_magnet = await service.handle_update(fake_db, update_magnet, task_service=task_service)
    assert reply_magnet is not None
    assert "Task Created!" in reply_magnet
    assert "Ubuntu.iso" in reply_magnet
    assert len(fake_db.tasks) == 1

    # /add command with HTTP URL (allow_local=DEBUG=True)
    update_url = {
        "update_id": 11,
        "message": {
            "chat": {"id": 11223344},
            "text": "/add https://distro.example.org/debian.iso",
        },
    }
    reply_url = await service.handle_update(fake_db, update_url, task_service=task_service)
    assert reply_url is not None
    assert "Task Created!" in reply_url
    assert len(fake_db.tasks) == 2


@pytest.mark.asyncio
async def test_telegram_add_ssrf_protection(fake_db: FakeAsyncSession, test_user: User) -> None:
    """Test SSRF blocked URLs are rejected when DEBUG=False."""
    test_user.telegram_chat_id = "11223344"
    fake_db.users[test_user.id] = test_user
    service = TelegramBotService(Settings(DEBUG=False))
    task_service = TaskService()

    update_private = {
        "update_id": 12,
        "message": {"chat": {"id": 11223344}, "text": "/add http://127.0.0.1/malicious.iso"},
    }
    reply_private = await service.handle_update(fake_db, update_private, task_service=task_service)
    assert reply_private is not None
    assert "Blocked URL" in reply_private
    # Task should not be created
    assert len(fake_db.tasks) == 0


@pytest.mark.asyncio
async def test_telegram_status_and_library_commands(
    fake_db: FakeAsyncSession, test_user: User
) -> None:
    """Test /status and /library Telegram commands."""
    test_user.telegram_chat_id = "55667788"
    fake_db.users[test_user.id] = test_user
    service = TelegramBotService(Settings())
    task_service = TaskService()

    # /status when no active tasks
    update_status = {
        "update_id": 20,
        "message": {"chat": {"id": 55667788}, "text": "/status"},
    }
    reply = await service.handle_update(fake_db, update_status, task_service=task_service)
    assert reply is not None
    assert "No downloads currently running" in reply

    # Create active task
    active_task = Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Fedora-40-Workstation.iso",
        source_uri="magnet:?xt=urn:btih:fedora",
        state="downloading",
        progress=45.6,
    )
    fake_db.tasks[active_task.id] = active_task

    reply2 = await service.handle_update(fake_db, update_status, task_service=task_service)
    assert reply2 is not None
    assert "Active Tasks" in reply2
    assert "Fedora-40-Workstation.iso" in reply2
    assert "45.6%" in reply2

    # /library with mock LibraryService
    mock_lib = AsyncMock(spec=LibraryService)
    from app.schemas.files import FileItemResponse, FileListResponse

    mock_lib.list_files.return_value = FileListResponse(
        current_folder_id="root",
        breadcrumbs=[],
        files=[
            FileItemResponse(
                id="drive-f-1",
                name="ArchLinux.iso",
                parent_id="root",
                mime_type="application/octet-stream",
                is_folder=False,
                size_bytes=1048576000,
            )
        ],
    )

    update_lib = {
        "update_id": 21,
        "message": {"chat": {"id": 55667788}, "text": "/library"},
    }
    reply_lib = await service.handle_update(
        fake_db, update_lib, task_service=task_service, library_service=mock_lib
    )
    assert reply_lib is not None
    assert "Recent Drive Files" in reply_lib
    assert "ArchLinux.iso" in reply_lib


@pytest.mark.asyncio
async def test_telegram_notifications(fake_db: FakeAsyncSession, test_user: User) -> None:
    """Test send_task_notification sends formatted message via Telegram API."""
    test_user.telegram_chat_id = "998877"
    fake_db.users[test_user.id] = test_user

    captured_requests: list[dict[str, Any]] = []

    def mock_tg_handler(request: httpx.Request) -> httpx.Response:
        import json

        data = json.loads(request.read().decode())
        captured_requests.append(data)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(mock_tg_handler)
    mock_client = httpx.AsyncClient(transport=transport)

    service = TelegramBotService(
        settings=Settings(TELEGRAM_BOT_TOKEN="mock_bot_token_123"),
        client=mock_client,
    )

    task = Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="BigBuckBunny_1080p.mp4",
        source_uri="https://example.com/video.mp4",
        state="completed",
        size_bytes=1073741824,  # 1.0 GB
    )

    # 1. Completion notification
    ok = await service.send_task_notification(
        db=fake_db,
        user_id=test_user.id,
        event_name="task.completed",
        task=task,
    )
    assert ok is True
    assert len(captured_requests) == 1
    assert captured_requests[0]["chat_id"] == "998877"
    assert "Download Complete!" in captured_requests[0]["text"]
    assert "BigBuckBunny_1080p.mp4" in captured_requests[0]["text"]
    assert "1.0 GB" in captured_requests[0]["text"]

    # 2. Failure notification
    task.state = "error"
    task.error = "Connection timeout during download"
    ok_fail = await service.send_task_notification(
        db=fake_db,
        user_id=test_user.id,
        event_name="task.failed",
        task=task,
    )
    assert ok_fail is True
    assert len(captured_requests) == 2
    assert "Download Failed" in captured_requests[1]["text"]
    assert "Connection timeout during download" in captured_requests[1]["text"]


@pytest.mark.asyncio
async def test_telegram_api_endpoints(fake_db: FakeAsyncSession, test_user: User) -> None:
    """Test /api/telegram/status, /api/telegram/link-code, /api/telegram/link, and /webhook."""
    fake_db.users[test_user.id] = test_user
    app = create_app(
        Settings(
            DEBUG=True,
            TELEGRAM_BOT_USERNAME="DriveSeedAppBot",
            TELEGRAM_WEBHOOK_SECRET="secret_webhook_token_99",
        )
    )
    app.dependency_overrides[get_db_session] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: test_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # 1. Status (initially not linked)
        resp = await client.get("/api/telegram/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_linked"] is False
        assert data["bot_username"] == "DriveSeedAppBot"

        # 2. Generate link code
        resp_code = await client.post("/api/telegram/link-code")
        assert resp_code.status_code == 200
        code_data = resp_code.json()
        assert len(code_data["code"]) == 6
        assert "start=" in code_data["deep_link"]

        # 3. Webhook call with invalid secret token -> 403
        resp_bad_secret = await client.post(
            "/api/telegram/webhook",
            json={"update_id": 100, "message": {"chat": {"id": 123}, "text": "/help"}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_secret"},
        )
        assert resp_bad_secret.status_code == 403

        # 4. Webhook call with valid secret token linking the account
        resp_webhook = await client.post(
            "/api/telegram/webhook",
            json={
                "update_id": 101,
                "message": {
                    "chat": {"id": 55443322},
                    "text": f"/start {code_data['code']}",
                },
            },
            headers={"X-Telegram-Bot-Api-Secret-Token": "secret_webhook_token_99"},
        )
        assert resp_webhook.status_code == 200
        assert resp_webhook.json() == {"ok": True}

        # 5. Check status is now linked
        resp_status2 = await client.get("/api/telegram/status")
        assert resp_status2.status_code == 200
        assert resp_status2.json()["is_linked"] is True
        assert resp_status2.json()["chat_id"] == "55443322"

        # 6. Unlink via DELETE /api/telegram/link
        resp_unlink = await client.delete("/api/telegram/link")
        assert resp_unlink.status_code == 204

        # 7. Check status is unlinked again
        resp_status3 = await client.get("/api/telegram/status")
        assert resp_status3.status_code == 200
        assert resp_status3.json()["is_linked"] is False
