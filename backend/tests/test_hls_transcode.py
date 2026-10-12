"""Tests for on-demand FFmpeg HLS transcoding service and API endpoints."""

import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import get_current_user
from app.api.stream import get_hls_service
from app.core.config import Settings
from app.interfaces.types import StoredFile
from app.main import app
from app.models.user import User
from app.services.stream import MediaProxyDisabledError
from app.services.transcode import (
    HlsTranscodeService,
    TranscodeCapExceededError,
)
from tests.fakes.fake_storage import FakeStorageBackend

# ---------------------------------------------------------------------------
# Unit tests: Format detection and Colab profile guard
# ---------------------------------------------------------------------------


def test_needs_transcoding_formats() -> None:
    service = HlsTranscodeService()

    # Formats requiring transcoding
    assert service.needs_transcoding("Movie.mkv") is True
    assert service.needs_transcoding("clip.avi") is True
    assert service.needs_transcoding("stream.ts") is True
    assert service.needs_transcoding("video.wmv") is True
    assert service.needs_transcoding("video.flv") is True
    assert service.needs_transcoding("file.dat", "video/x-matroska") is True

    # Native direct-play formats
    assert service.needs_transcoding("Movie.mp4") is False
    assert service.needs_transcoding("animation.webm") is False
    assert service.needs_transcoding("song.mp3") is False


@pytest.mark.asyncio
async def test_colab_profile_disables_hls_transcoding() -> None:
    colab_settings = Settings(PROFILE="colab")
    service = HlsTranscodeService(settings=colab_settings)
    test_user = User(id=uuid.uuid4(), google_sub="sub-colab", email="colab@test.com")

    with pytest.raises(MediaProxyDisabledError):
        await service.get_or_start_transcode(test_user, "file-123")

    with pytest.raises(MediaProxyDisabledError):
        await service.get_segment_path(test_user, "file-123", "segment_000.ts")


# ---------------------------------------------------------------------------
# Unit tests: Concurrency cap & path traversal guards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcode_concurrency_cap(tmp_path: Path) -> None:
    settings = Settings(
        TEMP_DOWNLOAD_DIR=str(tmp_path),
        MAX_CONCURRENT_TRANSCODES=1,
    )
    fake_storage = FakeStorageBackend()
    service = HlsTranscodeService(settings=settings, storage=fake_storage)
    test_user = User(id=uuid.uuid4(), google_sub="sub-1", email="user@test.com")

    # Seed files in storage
    fake_storage.files["file-1"] = StoredFile(
        id="file-1",
        name="vid1.mkv",
        parent_id="root",
        mime_type="video/x-matroska",
        size_bytes=1000,
    )
    fake_storage.files["file-2"] = StoredFile(
        id="file-2",
        name="vid2.mkv",
        parent_id="root",
        mime_type="video/x-matroska",
        size_bytes=1000,
    )

    # Manually create an in-flight session
    out_dir = tmp_path / "hls" / "file-1"
    out_dir.mkdir(parents=True, exist_ok=True)
    fake_proc = type("MockProcess", (), {"returncode": None})()
    import asyncio
    from typing import cast

    from app.services.transcode import TranscodeSession

    service._sessions[f"{test_user.id}:file-1"] = TranscodeSession(
        file_id="file-1",
        user_id=str(test_user.id),
        output_dir=out_dir,
        process=cast(asyncio.subprocess.Process, fake_proc),
        is_complete=False,
    )

    # Attempting to start a second transcode exceeds limit of 1
    with pytest.raises(TranscodeCapExceededError):
        await service.get_or_start_transcode(test_user, "file-2")


@pytest.mark.asyncio
async def test_segment_path_traversal_protection(tmp_path: Path) -> None:
    settings = Settings(TEMP_DOWNLOAD_DIR=str(tmp_path))
    service = HlsTranscodeService(settings=settings)
    test_user = User(id=uuid.uuid4(), google_sub="sub-1", email="user@test.com")

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await service.get_segment_path(test_user, "file-1", "../secret.txt")
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# API tests: GET /hls/{file_id}/index.m3u8 and GET /hls/{file_id}/{segment}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hls_api_endpoints_and_colab_rejection(tmp_path: Path) -> None:
    file_id = "test-hls-media"
    test_user = User(id=uuid.uuid4(), google_sub="sub-api", email="api@test.com")

    # 1. Test PROFILE=colab rejection on API routes
    colab_settings = Settings(PROFILE="colab", TEMP_DOWNLOAD_DIR=str(tmp_path))
    colab_service = HlsTranscodeService(settings=colab_settings)

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_hls_service] = lambda: colab_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_colab_playlist = await client.get(f"/hls/{file_id}/index.m3u8")
        assert res_colab_playlist.status_code == 403
        assert res_colab_playlist.json()["detail"]["error"]["code"] == "MEDIA_PROXY_DISABLED"

        res_colab_segment = await client.get(f"/hls/{file_id}/segment_000.ts")
        assert res_colab_segment.status_code == 403

    # 2. Test successful playlist and segment retrieval under standard server profile
    server_settings = Settings(PROFILE="server", TEMP_DOWNLOAD_DIR=str(tmp_path))
    fake_storage = FakeStorageBackend()
    fake_storage.files[file_id] = StoredFile(
        id=file_id,
        name="Feature.mkv",
        parent_id="folder_root",
        mime_type="video/x-matroska",
        size_bytes=10000000,
    )

    server_service = HlsTranscodeService(settings=server_settings, storage=fake_storage)

    # Pre-populate simulated HLS transcode output
    hls_dir = tmp_path / "hls" / file_id
    hls_dir.mkdir(parents=True, exist_ok=True)

    playlist_content = (
        "#EXTM3U\n"
        "#EXT-X-VERSION:3\n"
        "#EXT-X-TARGETDURATION:4\n"
        "#EXTINF:4.000,\n"
        "segment_000.ts\n"
        "#EXTINF:4.000,\n"
        "segment_001.ts\n"
        "#EXT-X-ENDLIST\n"
    )
    (hls_dir / "index.m3u8").write_text(playlist_content, encoding="utf-8")
    (hls_dir / "segment_000.ts").write_bytes(b"TS_PACKET_DATA_000")
    (hls_dir / "segment_001.ts").write_bytes(b"TS_PACKET_DATA_001")

    app.dependency_overrides[get_hls_service] = lambda: server_service

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Fetch playlist
        res_playlist = await client.get(f"/hls/{file_id}/index.m3u8")
        assert res_playlist.status_code == 200
        assert "application/vnd.apple.mpegurl" in res_playlist.headers.get("content-type", "")
        assert "segment_000.ts" in res_playlist.text

        # Fetch first segment
        res_seg = await client.get(f"/hls/{file_id}/segment_000.ts")
        assert res_seg.status_code == 200
        assert "video/mp2t" in res_seg.headers.get("content-type", "")
        assert res_seg.content == b"TS_PACKET_DATA_000"

        # Fetch non-existent segment -> 404
        res_404 = await client.get(f"/hls/{file_id}/segment_999.ts")
        assert res_404.status_code == 404

    app.dependency_overrides.clear()
