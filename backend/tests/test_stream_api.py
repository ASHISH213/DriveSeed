"""Tests for Range streaming proxy API and ProxyStreamer service (RFC 7233)."""

import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import get_current_user
from app.api.stream import get_streamer
from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.security import create_session_token
from app.interfaces.types import StoredFile
from app.main import create_app
from app.models.task import Task
from app.models.user import User
from app.services.stream import ProxyStreamer
from app.services.torrent import TorrentEngine, set_torrent_engine
from tests.fakes.fake_db import FakeAsyncSession
from tests.fakes.fake_storage import FakeStorageBackend
from tests.fakes.fake_torrent import FakeTorrentSession


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


@pytest.mark.asyncio
async def test_stream_concurrency_cap_exceeded(
    app_with_streamer,
    test_user: User,
    fake_storage: FakeStorageBackend,
) -> None:
    """Verify requesting more than concurrent streams limit yields HTTP 429."""
    from app.core.rate_limit import get_stream_concurrency_limiter

    limiter = get_stream_concurrency_limiter()
    limiter.reset()

    # Pre-populate 3 files in fake storage
    for i in range(1, 4):
        fid = f"stream_file_{i}"
        content = b"X" * 500
        fake_storage.files[fid] = StoredFile(
            id=fid,
            name=f"stream_file_{i}.mp4",
            parent_id="root_folder_stream",
            mime_type="video/mp4",
            size_bytes=len(content),
        )
        fake_storage.file_data[fid] = content

    # Simulate 2 active distinct file streams already acquired for test_user
    await limiter.acquire(str(test_user.id), "stream_file_1")
    await limiter.acquire(str(test_user.id), "stream_file_2")

    transport = ASGITransport(app=app_with_streamer)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Requesting stream_file_1 again succeeds (concurrent range chunk on active file)
        res1 = await client.get("/api/stream/stream_file_1", headers={"Range": "bytes=0-10"})
        assert res1.status_code == 206

        # Requesting a 3rd distinct file triggers 429 stream_cap_exceeded
        res3 = await client.get("/api/stream/stream_file_3", headers={"Range": "bytes=0-10"})
        assert res3.status_code == 429
        body = res3.json()
        assert body["detail"]["error"]["code"] == "stream_cap_exceeded"

    limiter.reset()


@pytest.mark.asyncio
async def test_stream_task_media_colab_refusal(test_user: User) -> None:
    """Hard Rule: Task streaming refuses with HTTP 403 under PROFILE=colab."""
    colab_settings = Settings(PROFILE="colab")
    colab_app = create_app(colab_settings)
    colab_app.dependency_overrides[get_current_user] = lambda: test_user
    colab_app.dependency_overrides[get_db_session] = lambda: FakeAsyncSession()
    colab_app.dependency_overrides[get_settings] = lambda: colab_settings
    transport = ASGITransport(app=colab_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/stream/task/{uuid.uuid4()}")
        assert res.status_code == 403
        assert res.json()["detail"]["error"]["code"] == "MEDIA_PROXY_DISABLED"


@pytest.mark.asyncio
async def test_stream_task_media_not_found(test_user: User) -> None:
    """Verify streaming a non-existent task returns HTTP 404."""
    fake_db = FakeAsyncSession()
    app = create_app(Settings(PROFILE="server"))
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db_session] = lambda: fake_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/stream/task/{uuid.uuid4()}")
        assert res.status_code == 404
        assert res.json()["detail"]["error"]["code"] == "TASK_NOT_FOUND"


@pytest.mark.asyncio
async def test_stream_task_media_buffer_too_small(test_user: User) -> None:
    """Verify HTTP 425 BUFFER_TOO_SMALL when scratch file is missing or <1KB."""
    fake_db = FakeAsyncSession()
    task = Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        source_type="magnet",
        source_uri="magnet:?xt=urn:btih:da39a3ee5e6b4b0d3255bfef95601890afd80709&dn=Movie.mp4",
        name="Movie.mp4",
        state="downloading",
        size_bytes=100000,
    )
    fake_db.add(task)

    with tempfile.TemporaryDirectory() as temp_dir:
        settings = Settings(TEMP_DOWNLOAD_DIR=temp_dir, PROFILE="server")
        app = create_app(settings)
        app.dependency_overrides[get_current_user] = lambda: test_user
        app.dependency_overrides[get_db_session] = lambda: fake_db
        app.dependency_overrides[get_settings] = lambda: settings

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(f"/api/stream/task/{task.id}")
            assert res.status_code == 404  # directory not found yet

            # Create folder with empty/small file (< 1024 bytes)
            task_dir = Path(temp_dir) / str(task.id)
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / "Movie.mp4").write_bytes(b"small" * 10)

            res2 = await client.get(f"/api/stream/task/{task.id}")
            assert res2.status_code == 425
            assert res2.json()["detail"]["error"]["code"] == "BUFFER_TOO_SMALL"


@pytest.mark.asyncio
async def test_stream_task_media_success_and_range_requests(test_user: User) -> None:
    """Verify active task range streaming, Content-Range headers, and 206 Partial Content."""
    fake_db = FakeAsyncSession()
    task = Task(
        id=uuid.uuid4(),
        user_id=test_user.id,
        source_type="magnet",
        source_uri="magnet:?xt=urn:btih:da39a3ee5e6b4b0d3255bfef95601890afd80709&dn=Movie.mp4",
        name="Movie.mp4",
        state="downloading",
        size_bytes=200000,
    )
    fake_db.add(task)

    fake_session = FakeTorrentSession()
    mock_engine = TorrentEngine(
        settings=Settings(PROFILE="server"), session_factory=lambda: fake_session
    )
    set_torrent_engine(mock_engine)

    with tempfile.TemporaryDirectory() as temp_dir:
        settings = Settings(TEMP_DOWNLOAD_DIR=temp_dir, PROFILE="server")
        app = create_app(settings)
        app.dependency_overrides[get_current_user] = lambda: test_user
        app.dependency_overrides[get_db_session] = lambda: fake_db
        app.dependency_overrides[get_settings] = lambda: settings

        task_dir = Path(temp_dir) / str(task.id)
        task_dir.mkdir(parents=True, exist_ok=True)
        # 10,000 bytes downloaded so far
        file_content = b"V" * 10000
        (task_dir / "Movie.mp4").write_bytes(file_content)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Full request
            res_full = await client.get(f"/api/stream/task/{task.id}")
            assert res_full.status_code == 200
            assert res_full.headers["accept-ranges"] == "bytes"
            assert res_full.headers["content-length"] == "10000"
            assert res_full.content == file_content

            # 2. Range request within downloaded range
            res_range = await client.get(
                f"/api/stream/task/{task.id}", headers={"Range": "bytes=0-1023"}
            )
            assert res_range.status_code == 206
            assert res_range.headers["content-range"] == "bytes 0-1023/200000"
            assert res_range.headers["content-length"] == "1024"
            assert res_range.content == file_content[:1024]

            # 3. Seeking past currently downloaded bytes (e.g. 50,000 when 10,000 downloaded)
            res_unsat = await client.get(
                f"/api/stream/task/{task.id}", headers={"Range": "bytes=50000-"}
            )
            assert res_unsat.status_code == 416
            assert res_unsat.headers["content-range"] == "bytes */10000"

    set_torrent_engine(None)
