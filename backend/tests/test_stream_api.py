"""Tests for Range streaming proxy API and ProxyStreamer service (RFC 7233)."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import get_current_user
from app.api.stream import get_streamer
from app.core.config import Settings
from app.core.security import create_session_token
from app.interfaces.types import StoredFile
from app.main import create_app
from app.models.user import User
from app.services.stream import ProxyStreamer
from tests.fakes.fake_storage import FakeStorageBackend


@pytest.fixture
def test_user() -> User:
    """Fixture providing a test user."""
    return User(
        id=uuid.uuid4(),
        google_sub="sub_stream_123",
        email="streamer@driveseed.io",
        drive_refresh_token_enc="encrypted_token_dummy",
        drive_root_folder_id="root_folder_stream",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def fake_storage(test_user: User) -> FakeStorageBackend:
    """Fixture providing FakeStorageBackend pre-populated with a sample video file."""
    storage = FakeStorageBackend()
    storage.user_roots[str(test_user.id)] = "root_folder_stream"
    storage.folders["root_folder_stream"] = "DriveSeed"

    file_id = "sample_mp4_file_id"
    # Create 1000 bytes of deterministic test payload
    sample_content = b"".join(f"{i:04d}".encode("ascii") for i in range(250))
    storage.files[file_id] = StoredFile(
        id=file_id,
        name="test_video.mp4",
        parent_id="root_folder_stream",
        mime_type="video/mp4",
        size_bytes=len(sample_content),
        md5="sample_md5_hash",
    )
    storage.file_data[file_id] = sample_content
    return storage


@pytest.fixture
def app_with_streamer(test_user: User, fake_storage: FakeStorageBackend):
    """FastAPI app instance with overridden dependencies for testing."""
    app = create_app(Settings(PROFILE="server"))

    app.dependency_overrides[get_current_user] = lambda: test_user
    streamer = ProxyStreamer(settings=Settings(PROFILE="server"), storage=fake_storage)
    app.dependency_overrides[get_streamer] = lambda: streamer

    return app


@pytest.mark.asyncio
async def test_stream_unauthenticated(fake_storage: FakeStorageBackend) -> None:
    """Verify unauthenticated requests to /stream/{file_id} are rejected with 401."""
    app = create_app(Settings(PROFILE="server"))
    streamer = ProxyStreamer(settings=Settings(PROFILE="server"), storage=fake_storage)
    app.dependency_overrides[get_streamer] = lambda: streamer

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        res = await client.get("/stream/sample_mp4_file_id")
        assert res.status_code == 401
        assert res.json()["detail"]["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_stream_file_not_found(app_with_streamer) -> None:
    """Verify requesting a non-existent file returns 404 FILE_NOT_FOUND."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_streamer),
        base_url="http://test",
    ) as client:
        res = await client.get("/stream/non_existent_id")
        assert res.status_code == 404
        assert res.json()["detail"]["error"]["code"] == "FILE_NOT_FOUND"


@pytest.mark.asyncio
async def test_stream_full_content_200(
    app_with_streamer,
    fake_storage: FakeStorageBackend,
) -> None:
    """Verify requesting without Range header returns full file with 200 OK and Accept-Ranges."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_streamer),
        base_url="http://test",
    ) as client:
        res = await client.get("/stream/sample_mp4_file_id")
        assert res.status_code == 200
        assert res.headers["Accept-Ranges"] == "bytes"
        assert res.headers["Content-Type"] == "video/mp4"
        assert res.headers["Content-Length"] == "1000"
        assert "Content-Range" not in res.headers

        expected_bytes = fake_storage.file_data["sample_mp4_file_id"]
        assert res.content == expected_bytes


@pytest.mark.asyncio
async def test_stream_partial_content_range_requests(
    app_with_streamer,
    fake_storage: FakeStorageBackend,
) -> None:
    """Verify range requests return 206 Partial Content with correct Content-Range and bytes."""
    full_data = fake_storage.file_data["sample_mp4_file_id"]

    async with AsyncClient(
        transport=ASGITransport(app=app_with_streamer),
        base_url="http://test",
    ) as client:
        # 1. Start-End Range (0-499)
        res1 = await client.get(
            "/stream/sample_mp4_file_id",
            headers={"Range": "bytes=0-499"},
        )
        assert res1.status_code == 206
        assert res1.headers["Content-Range"] == "bytes 0-499/1000"
        assert res1.headers["Content-Length"] == "500"
        assert res1.headers["Accept-Ranges"] == "bytes"
        assert res1.content == full_data[0:500]

        # 2. Seeking to second half (500-999)
        res2 = await client.get(
            "/stream/sample_mp4_file_id",
            headers={"Range": "bytes=500-999"},
        )
        assert res2.status_code == 206
        assert res2.headers["Content-Range"] == "bytes 500-999/1000"
        assert res2.headers["Content-Length"] == "500"
        assert res2.content == full_data[500:1000]

        # 3. Open-ended Range (800-)
        res3 = await client.get(
            "/stream/sample_mp4_file_id",
            headers={"Range": "bytes=800-"},
        )
        assert res3.status_code == 206
        assert res3.headers["Content-Range"] == "bytes 800-999/1000"
        assert res3.headers["Content-Length"] == "200"
        assert res3.content == full_data[800:1000]

        # 4. Suffix Range (-250 -> last 250 bytes: 750-999)
        res4 = await client.get(
            "/stream/sample_mp4_file_id",
            headers={"Range": "bytes=-250"},
        )
        assert res4.status_code == 206
        assert res4.headers["Content-Range"] == "bytes 750-999/1000"
        assert res4.headers["Content-Length"] == "250"
        assert res4.content == full_data[750:1000]


@pytest.mark.asyncio
async def test_stream_range_not_satisfiable_416(app_with_streamer) -> None:
    """Verify out-of-bounds or malformed range requests return 416 Range Not Satisfiable."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_streamer),
        base_url="http://test",
    ) as client:
        # Out of bounds (starts beyond file size)
        res = await client.get(
            "/stream/sample_mp4_file_id",
            headers={"Range": "bytes=2000-3000"},
        )
        assert res.status_code == 416
        assert res.headers["Content-Range"] == "bytes */1000"

        # Invalid start > end
        res_inv = await client.get(
            "/stream/sample_mp4_file_id",
            headers={"Range": "bytes=500-100"},
        )
        assert res_inv.status_code == 416
        assert res_inv.headers["Content-Range"] == "bytes */1000"

        # Malformed
        res_mal = await client.get(
            "/stream/sample_mp4_file_id",
            headers={"Range": "bytes=invalid"},
        )
        assert res_mal.status_code == 416
        assert res_mal.headers["Content-Range"] == "bytes */1000"


@pytest.mark.asyncio
async def test_stream_via_api_alias(app_with_streamer, fake_storage: FakeStorageBackend) -> None:
    """Verify /api/stream/{file_id} alias works identically to /stream/{file_id}."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_streamer),
        base_url="http://test",
    ) as client:
        res = await client.get(
            "/api/stream/sample_mp4_file_id",
            headers={"Range": "bytes=100-199"},
        )
        assert res.status_code == 206
        assert res.headers["Content-Range"] == "bytes 100-199/1000"
        assert res.headers["Content-Length"] == "100"
        assert res.content == fake_storage.file_data["sample_mp4_file_id"][100:200]


@pytest.mark.asyncio
async def test_stream_auth_via_query_token(
    fake_storage: FakeStorageBackend,
    test_user: User,
) -> None:
    """Verify HTML5 media player can authenticate via ?token= query parameter."""
    app = create_app(Settings(PROFILE="server"))
    token = create_session_token(user_id=str(test_user.id))

    # Mock user retrieval via session token
    from app.api.auth import get_auth_service
    from app.services.auth import AuthService

    class FakeAuthService(AuthService):
        async def get_current_user(self, db, session_token: str | None) -> User | None:
            if session_token == token:
                return test_user
            return None

    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(
        settings=Settings(PROFILE="server")
    )
    streamer = ProxyStreamer(settings=Settings(PROFILE="server"), storage=fake_storage)
    app.dependency_overrides[get_streamer] = lambda: streamer

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        res = await client.get(f"/stream/sample_mp4_file_id?token={token}")
        assert res.status_code == 200
        assert res.headers["Content-Length"] == "1000"


@pytest.mark.asyncio
async def test_colab_profile_disables_media_proxying(
    test_user: User,
    fake_storage: FakeStorageBackend,
) -> None:
    """Hard Rule: verify PROFILE=colab strictly disables media proxying and returns 403."""
    app = create_app(Settings(PROFILE="colab"))
    app.dependency_overrides[get_current_user] = lambda: test_user
    streamer = ProxyStreamer(settings=Settings(PROFILE="colab"), storage=fake_storage)
    app.dependency_overrides[get_streamer] = lambda: streamer

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        res = await client.get("/stream/sample_mp4_file_id")
        assert res.status_code == 403
        data = res.json()
        assert data["detail"]["error"]["code"] == "MEDIA_PROXY_DISABLED"


@pytest.mark.asyncio
async def test_stream_midstream_token_refresh(test_user: User) -> None:
    """Verify that when token expires mid-stream (401), DriveApiStorage refreshes and continues."""
    from typing import Any

    from app.services.drive import DriveApiStorage

    call_count = 0
    token_refreshed = False

    class ExpiringDriveService:
        def files(self) -> Any:
            return self

        def get(self, fileId: str, fields: str = "") -> Any:
            class GetReq:
                def execute(self) -> dict[str, Any]:
                    return {
                        "id": fileId,
                        "name": "stream_refresh.mp4",
                        "size": "2000",
                        "mimeType": "video/mp4",
                        "parents": ["root"],
                    }

            return GetReq()

        def get_media(self, fileId: str) -> Any:
            nonlocal call_count, token_refreshed

            class MediaReq:
                def __init__(self) -> None:
                    self.headers: dict[str, str] = {}

                def execute(self) -> bytes:
                    nonlocal call_count, token_refreshed
                    call_count += 1
                    if call_count == 1:
                        # First attempt raises 401 token expired
                        raise Exception("401 Unauthorized: access token expired")
                    # Second attempt after re-acquiring credentials succeeds
                    token_refreshed = True
                    return b"Y" * 1000

            return MediaReq()

    storage = DriveApiStorage(
        client_factory=lambda _u: ExpiringDriveService(),
    )

    chunks = [c async for c in storage.open_range(test_user, "file_midstream", 0, 999)]
    assert token_refreshed is True
    assert len(b"".join(chunks)) == 1000
