"""Tests for subtitle detection, SRT to WebVTT conversion, and API endpoints."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import get_current_user
from app.api.files import get_subtitle_service
from app.interfaces.types import StoredFile
from app.main import app
from app.models.user import User
from app.services.subtitles import (
    SubtitleService,
    convert_srt_to_vtt,
    parse_subtitle_info,
)
from tests.fakes.fake_storage import FakeStorageBackend

# ---------------------------------------------------------------------------
# Unit tests: SRT to WebVTT converter & filename parser
# ---------------------------------------------------------------------------


def test_convert_srt_to_vtt_basic() -> None:
    srt_data = (
        "1\n"
        "00:00:01,000 --> 00:00:04,500\n"
        "Hello world!\n\n"
        "2\n"
        "00:00:05,250 --> 00:00:08,750\n"
        "This is a second subtitle line.\n"
    )
    vtt = convert_srt_to_vtt(srt_data)
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:01.000 --> 00:00:04.500" in vtt
    assert "00:00:05.250 --> 00:00:08.750" in vtt
    assert "Hello world!" in vtt
    assert "This is a second subtitle line." in vtt


def test_convert_srt_to_vtt_bom_and_crlf() -> None:
    srt_data = "\ufeff1\r\n00:01:23,456 --> 00:01:25,789\r\n<i>Italic caption</i>\r\n\r\n"
    vtt = convert_srt_to_vtt(srt_data)
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:01:23.456 --> 00:01:25.789" in vtt
    assert "<i>Italic caption</i>" in vtt
    assert "\ufeff" not in vtt
    assert "\r" not in vtt


def test_convert_srt_to_vtt_already_vtt() -> None:
    already_vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nAlready VTT"
    assert convert_srt_to_vtt(already_vtt) == already_vtt


def test_convert_srt_to_vtt_empty() -> None:
    assert convert_srt_to_vtt("") == "WEBVTT\n\n"


def test_parse_subtitle_info() -> None:
    # Exact language code
    lang, label = parse_subtitle_info("movie.en.srt", "movie")
    assert lang == "en"
    assert label == "English"

    # Three-letter language code
    lang, label = parse_subtitle_info("BigBuckBunny.spa.vtt", "BigBuckBunny")
    assert lang == "es"
    assert label == "Spanish"

    # Full name and forced tag
    lang, label = parse_subtitle_info("Avatar.French.forced.srt", "Avatar")
    assert lang == "fr"
    assert "French" in label
    assert "Forced" in label

    # SDH modifier
    lang, label = parse_subtitle_info("film.en.sdh.srt", "film")
    assert lang == "en"
    assert "SDH" in label

    # Generic default
    lang, label = parse_subtitle_info("standalone.srt", "standalone")
    assert lang == "und"
    assert label == "Default"


# ---------------------------------------------------------------------------
# Integration tests: SubtitleService with FakeStorageBackend
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_storage() -> FakeStorageBackend:
    return FakeStorageBackend()


@pytest.fixture
def test_user() -> User:
    return User(
        id=uuid.uuid4(),
        google_sub="sub-subtitles-test",
        email="subtitles@test.com",
    )


@pytest.mark.asyncio
async def test_subtitle_service_discovery(
    fake_storage: FakeStorageBackend, test_user: User
) -> None:
    service = SubtitleService(storage=fake_storage)

    folder_id = "folder_media"
    video_id = "file_video1"

    # Video file
    fake_storage.files[video_id] = StoredFile(
        id=video_id,
        name="Episode.01.mkv",
        parent_id=folder_id,
        mime_type="video/x-matroska",
        size_bytes=1000000,
    )

    # Sidecar English SRT
    sub1_id = "file_sub_en"
    fake_storage.files[sub1_id] = StoredFile(
        id=sub1_id,
        name="Episode.01.en.srt",
        parent_id=folder_id,
        mime_type="application/x-subrip",
        size_bytes=500,
    )

    # Sidecar Spanish VTT
    sub2_id = "file_sub_es"
    fake_storage.files[sub2_id] = StoredFile(
        id=sub2_id,
        name="Episode.01.es.vtt",
        parent_id=folder_id,
        mime_type="text/vtt",
        size_bytes=600,
    )

    # Unrelated subtitle for another episode
    sub_other_id = "file_sub_ep2"
    fake_storage.files[sub_other_id] = StoredFile(
        id=sub_other_id,
        name="Episode.02.en.srt",
        parent_id=folder_id,
        mime_type="application/x-subrip",
        size_bytes=500,
    )

    # Add second video to prove prefix filtering works
    fake_storage.files["file_video2"] = StoredFile(
        id="file_video2",
        name="Episode.02.mkv",
        parent_id=folder_id,
        mime_type="video/x-matroska",
        size_bytes=1000000,
    )

    resp = await service.list_subtitles(test_user, video_id)
    assert len(resp.subtitles) == 2
    track_ids = {t.id for t in resp.subtitles}
    assert sub1_id in track_ids
    assert sub2_id in track_ids
    assert sub_other_id not in track_ids


@pytest.mark.asyncio
async def test_subtitle_service_get_content(
    fake_storage: FakeStorageBackend, test_user: User
) -> None:
    service = SubtitleService(storage=fake_storage)

    sub_id = "file_sub_1"
    srt_body = b"1\n00:00:10,000 --> 00:00:12,000\nTest subtitle content\n"

    fake_storage.files[sub_id] = StoredFile(
        id=sub_id,
        name="video.en.srt",
        parent_id="folder_1",
        mime_type="application/x-subrip",
        size_bytes=len(srt_body),
    )
    fake_storage.file_data[sub_id] = srt_body

    vtt = await service.get_subtitle_content(test_user, "vid_1", sub_id)
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:10.000 --> 00:00:12.000" in vtt
    assert "Test subtitle content" in vtt


# ---------------------------------------------------------------------------
# API endpoint tests: /api/files/{id}/subtitles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_list_and_get_subtitles(
    fake_storage: FakeStorageBackend, test_user: User
) -> None:
    video_id = "vid_123"
    sub_id = "sub_456"

    srt_bytes = b"1\n00:01:00,500 --> 00:01:05,500\nWelcome to DriveSeed!\n"

    fake_storage.files[video_id] = StoredFile(
        id=video_id,
        name="Demo.mp4",
        parent_id="folder_root",
        mime_type="video/mp4",
        size_bytes=5000000,
    )
    fake_storage.files[sub_id] = StoredFile(
        id=sub_id,
        name="Demo.en.srt",
        parent_id="folder_root",
        mime_type="application/x-subrip",
        size_bytes=len(srt_bytes),
    )
    fake_storage.file_data[sub_id] = srt_bytes

    service = SubtitleService(storage=fake_storage)
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_subtitle_service] = lambda: service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List subtitles
        res_list = await client.get(f"/api/files/{video_id}/subtitles")
        assert res_list.status_code == 200
        data = res_list.json()
        assert len(data["subtitles"]) == 1
        assert data["subtitles"][0]["id"] == sub_id
        assert data["subtitles"][0]["language"] == "en"
        assert data["subtitles"][0]["label"] == "English"
        assert data["subtitles"][0]["format"] == "srt"

        # 2. Get subtitle track as WebVTT
        res_track = await client.get(f"/api/files/{video_id}/subtitles/{sub_id}")
        assert res_track.status_code == 200
        assert "text/vtt" in res_track.headers.get("content-type", "")
        body = res_track.text
        assert body.startswith("WEBVTT\n\n")
        assert "00:01:00.500 --> 00:01:05.500" in body
        assert "Welcome to DriveSeed!" in body

        # 3. 404 on missing subtitle
        res_404 = await client.get(f"/api/files/{video_id}/subtitles/non_existent")
        assert res_404.status_code == 404

    app.dependency_overrides.clear()
