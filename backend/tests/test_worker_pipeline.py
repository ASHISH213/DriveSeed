"""Integration tests for worker pipeline: download -> upload to Drive -> verify -> temp cleanup."""

import contextlib
import tempfile
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from app.core.config import Settings
from app.core.security import encrypt_token
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreateRequest
from app.services.drive import DriveApiStorage
from app.services.http_download import HttpEngine
from app.services.task import TaskService
from app.workers.pipeline import process_download_task
from tests.fakes.fake_db import FakeAsyncSession
from tests.fakes.fake_google_drive import FakeGoogleDriveService
from tests.fakes.fake_queue import FakeTaskQueue


def make_mock_server_app(file_data: bytes, filename: str) -> Starlette:
    """Create Starlette test app for pipeline download verification."""

    async def download_handler(request: Request) -> Response:
        return Response(
            file_data,
            status_code=200,
            headers={
                "Content-Length": str(len(file_data)),
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    async def head_handler(request: Request) -> Response:
        return Response(
            status_code=200,
            headers={
                "Content-Length": str(len(file_data)),
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    async def error_handler(request: Request) -> Response:
        return Response(status_code=500, content="Internal Server Error")

    return Starlette(
        routes=[
            Route("/files/download", download_handler, methods=["GET"]),
            Route("/files/download", head_handler, methods=["HEAD"]),
            Route("/files/error", error_handler, methods=["GET", "HEAD"]),
        ]
    )


@pytest.mark.asyncio
async def test_worker_pipeline_full_lifecycle_and_temp_cleanup() -> None:
    """Verify download -> upload to Drive -> verify -> delete temp files -> completed."""
    fake_db = FakeAsyncSession()
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        google_sub="sub-pipeline-test",
        email="pipeliner@example.com",
        drive_refresh_token_enc=encrypt_token("valid_refresh_token_123"),
        drive_root_folder_id=None,
        created_at=datetime.now(UTC),
    )
    fake_db.add(user)

    task_id = uuid.uuid4()
    task = Task(
        id=task_id,
        user_id=user_id,
        source_type="url",
        source_uri="https://public-cdn.example.com/files/download",
        name="linux-distro.iso",
        state="queued",
    )
    fake_db.add(task)

    # 15 KB test binary payload
    payload = bytes(i % 256 for i in range(15000))
    app = make_mock_server_app(payload, filename="linux-distro.iso")
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="https://public-cdn.example.com"
    ) as client:
        fake_drive = FakeGoogleDriveService()
        storage = DriveApiStorage(client_factory=lambda _u: fake_drive, chunk_size=4096)
        engine = HttpEngine(client=client, allow_local=True, chunk_size=2048)

        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(
                TEMP_DOWNLOAD_DIR=temp_dir,
                GOOGLE_CLIENT_ID="dummy_id",
                GOOGLE_CLIENT_SECRET="dummy_secret",
            )

            @contextlib.asynccontextmanager
            async def fake_session_factory() -> AsyncGenerator[FakeAsyncSession, None]:
                yield fake_db

            ctx = {
                "db_session_factory": fake_session_factory,
                "settings": settings,
                "download_engine": engine,
                "storage_backend": storage,
            }

            task_temp_folder = Path(temp_dir) / str(task.id)

            # Execute pipeline
            await process_download_task(ctx, str(task.id))

            # 1. Verify task completed
            assert task.state == "completed"
            assert task.progress == 1.0
            assert task.completed_at is not None
            assert task.error is None
            assert task.size_bytes == len(payload)

            # 2. Verify file exists in fake Google Drive with matching size and name
            drive_files = [
                f
                for f in fake_drive.files().store.values()
                if f.get("mimeType") != "application/vnd.google-apps.folder"
            ]
            assert len(drive_files) == 1
            uploaded = drive_files[0]
            assert uploaded["name"] == "linux-distro.iso"
            assert int(uploaded["size"]) == len(payload)
            assert uploaded["id"].startswith("gdrive_file_")

            # 3. Verify user's root folder was cached
            assert user.drive_root_folder_id is not None
            assert uploaded["parents"] == [user.drive_root_folder_id]

            # 4. HARD RULE: Verify local temp folder is completely deleted
            assert not task_temp_folder.exists()


@pytest.mark.asyncio
async def test_task_creation_enqueues_background_job() -> None:
    """Verify creating a task via TaskService enqueues process_download_task."""
    fake_db = FakeAsyncSession()
    user = User(
        id=uuid.uuid4(),
        google_sub="sub-enqueue-test",
        email="enqueuer@example.com",
    )
    fake_db.add(user)

    fake_queue = FakeTaskQueue()
    task_service = TaskService(queue=fake_queue)

    req = TaskCreateRequest(
        source_uri="https://example.com/archive.zip",
        name="archive.zip",
    )
    created_task = await task_service.create_task(db=fake_db, user=user, request=req)

    assert len(fake_queue.jobs) == 1
    job = fake_queue.jobs[0]
    assert job["name"] == "process_download_task"
    assert job["kwargs"]["task_id"] == str(created_task.id)


@pytest.mark.asyncio
async def test_pipeline_handles_failure_and_cleans_up_temp() -> None:
    """Verify task failure transitions to 'failed', records error, and deletes temp files."""
    fake_db = FakeAsyncSession()
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        google_sub="sub-fail-test",
        email="fail@example.com",
        drive_refresh_token_enc=encrypt_token("tok"),
    )
    fake_db.add(user)

    task_id = uuid.uuid4()
    task = Task(
        id=task_id,
        user_id=user_id,
        source_type="url",
        source_uri="https://public-cdn.example.com/files/error",
        name="fail.bin",
        state="queued",
    )
    fake_db.add(task)

    app = make_mock_server_app(b"", filename="fail.bin")
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="https://public-cdn.example.com"
    ) as client:
        fake_drive = FakeGoogleDriveService()
        storage = DriveApiStorage(client_factory=lambda _u: fake_drive)
        engine = HttpEngine(client=client, allow_local=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(TEMP_DOWNLOAD_DIR=temp_dir)

            @contextlib.asynccontextmanager
            async def fake_session_factory() -> AsyncGenerator[FakeAsyncSession, None]:
                yield fake_db

            ctx = {
                "db_session_factory": fake_session_factory,
                "settings": settings,
                "download_engine": engine,
                "storage_backend": storage,
            }

            task_temp_folder = Path(temp_dir) / str(task.id)

            await process_download_task(ctx, str(task.id))

            # Verify task failed
            assert task.state == "failed"
            assert task.error is not None
            assert "Metadata fetch failed" in task.error or "HTTP request failed" in task.error

            # Verify temp files deleted on failure
            assert not task_temp_folder.exists()


@pytest.mark.asyncio
async def test_pipeline_fails_when_user_has_no_drive_token() -> None:
    """Verify pipeline immediately fails task if user has not authorized Google Drive."""
    fake_db = FakeAsyncSession()
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        google_sub="sub-no-token",
        email="notoken@example.com",
        drive_refresh_token_enc=None,  # No token!
    )
    fake_db.add(user)

    task_id = uuid.uuid4()
    task = Task(
        id=task_id,
        user_id=user_id,
        source_type="url",
        source_uri="https://example.com/file.bin",
        name="file.bin",
        state="queued",
    )
    fake_db.add(task)

    @contextlib.asynccontextmanager
    async def fake_session_factory() -> AsyncGenerator[FakeAsyncSession, None]:
        yield fake_db

    ctx = {"db_session_factory": fake_session_factory}

    await process_download_task(ctx, str(task.id))

    assert task.state == "failed"
    assert "not connected" in str(task.error)
