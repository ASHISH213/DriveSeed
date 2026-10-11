"""Unit and integration tests for SSRF guard and HttpEngine download with Range resume."""

import tempfile
import uuid
from pathlib import Path

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from app.core.ssrf import SSRFError, validate_url
from app.models.task import Task
from app.services.http_download import HttpEngine

# ============================================================================
# SSRF Guard Tests
# ============================================================================


@pytest.mark.asyncio
async def test_ssrf_rejects_loopback_and_private_ips() -> None:
    """Verify validate_url rejects IPv4 loopback, private, and cloud metadata IPs."""
    blocked_urls = [
        "http://127.0.0.1",
        "http://127.0.0.1:8000/test",
        "http://127.0.0.2:8080/data",
        "http://10.0.0.1/secret",
        "http://10.254.254.254",
        "http://172.16.0.1/admin",
        "http://172.31.255.255/admin",
        "http://192.168.0.1/router",
        "http://192.168.1.100:3000",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0:8000/",
        "http://100.64.0.1/",  # CGNAT
        "http://255.255.255.255/",
    ]
    for url in blocked_urls:
        with pytest.raises(SSRFError):
            await validate_url(url)


@pytest.mark.asyncio
async def test_ssrf_rejects_ipv6_loopback_and_local() -> None:
    """Verify validate_url rejects IPv6 loopback, link-local, and unique local addresses."""
    blocked_ipv6 = [
        "http://[::1]/",
        "http://[::1]:8080/status",
        "http://[fe80::1]/link-local",
        "http://[fc00::1]/unique-local",
        "http://[::ffff:127.0.0.1]/mapped-loopback",
        "http://[::ffff:169.254.169.254]/mapped-metadata",
    ]
    for url in blocked_ipv6:
        with pytest.raises(SSRFError):
            await validate_url(url)


@pytest.mark.asyncio
async def test_ssrf_rejects_local_hostnames_and_resolutions() -> None:
    """Verify validate_url blocks localhost hostnames and domains resolving to internal IPs."""
    # Obvious local hostnames
    with pytest.raises(SSRFError):
        await validate_url("http://localhost:8000")
    with pytest.raises(SSRFError):
        await validate_url("http://test.localhost")
    with pytest.raises(SSRFError):
        await validate_url("http://mycomputer.local")

    # Mock resolver returning internal IP for an arbitrary domain
    async def fake_dns_internal(host: str) -> list[str]:
        return ["127.0.0.1"]

    with pytest.raises(SSRFError, match="blocked IP"):
        await validate_url("http://example-internal.com", dns_resolver=fake_dns_internal)

    # Mock resolver returning public IP
    async def fake_dns_public(host: str) -> list[str]:
        return ["93.184.216.34"]

    # Should not raise
    await validate_url("http://example-public.com", dns_resolver=fake_dns_public)


@pytest.mark.asyncio
async def test_ssrf_rejects_non_http_schemes() -> None:
    """Verify validate_url blocks non-HTTP/HTTPS protocols."""
    disallowed = [
        "file:///etc/passwd",
        "ftp://ftp.example.com/file.zip",
        "gopher://127.0.0.1:70/",
        "data:text/plain;base64,SGVsbG8=",
        "javascript:alert(1)",
    ]
    for url in disallowed:
        with pytest.raises(SSRFError, match="Disallowed scheme"):
            await validate_url(url)


# ============================================================================
# Mock Server Fixtures for Download & Resume Testing
# ============================================================================


def make_mock_download_app(file_data: bytes, filename: str = "dataset.bin") -> Starlette:
    """Create a Starlette ASGI app providing Range-supported downloads and redirects."""

    async def download_handler(request: Request) -> Response:
        range_header = request.headers.get("range")
        total_len = len(file_data)
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Accept-Ranges": "bytes",
        }

        if range_header and range_header.startswith("bytes="):
            byte_range = range_header[6:].strip()
            start_str, _, end_str = byte_range.partition("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else total_len - 1

            if start >= total_len:
                return Response(status_code=416, headers={"Content-Range": f"bytes */{total_len}"})

            chunk = file_data[start : end + 1]
            headers["Content-Range"] = f"bytes {start}-{end}/{total_len}"
            headers["Content-Length"] = str(len(chunk))
            return Response(chunk, status_code=206, headers=headers)

        headers["Content-Length"] = str(total_len)
        return Response(file_data, status_code=200, headers=headers)

    async def head_handler(request: Request) -> Response:
        return Response(
            status_code=200,
            headers={
                "Content-Length": str(len(file_data)),
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Accept-Ranges": "bytes",
            },
        )

    async def redirect_to_internal(request: Request) -> Response:
        # Malicious redirect targeting loopback
        return Response(
            status_code=302,
            headers={"Location": "http://127.0.0.1:8000/internal-data"},
        )

    async def valid_redirect(request: Request) -> Response:
        # Valid redirect pointing to download endpoint
        return Response(
            status_code=302,
            headers={"Location": "/files/download"},
        )

    routes = [
        Route("/files/download", download_handler, methods=["GET"]),
        Route("/files/download", head_handler, methods=["HEAD"]),
        Route("/redirect/internal", redirect_to_internal, methods=["GET", "HEAD"]),
        Route("/redirect/valid", valid_redirect, methods=["GET", "HEAD"]),
    ]
    return Starlette(routes=routes)


# ============================================================================
# HttpEngine Download & Resume Tests
# ============================================================================


@pytest.mark.asyncio
async def test_http_engine_blocks_redirect_to_internal_ip() -> None:
    """Verify HttpEngine blocks redirects to internal loopback IPs."""
    test_data = b"Some public data"
    app = make_mock_download_app(test_data)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="https://public-cdn.example.com"
    ) as client:
        # Mock public DNS for public-cdn.example.com
        async def fake_dns(host: str) -> list[str]:
            return ["93.184.216.34"]

        engine = HttpEngine(client=client, dns_resolver=fake_dns)
        task = Task(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            source_type="url",
            source_uri="https://public-cdn.example.com/redirect/internal",
            name="redirect_test.bin",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            dest = Path(tmp_dir)
            with pytest.raises(SSRFError):
                async for _ in engine.start(task=task, selected=[0], dest=dest):
                    pass


@pytest.mark.asyncio
async def test_full_url_download_completes_successfully() -> None:
    """Verify downloading a URL end-to-end creates the file and tracks progress."""
    payload = b"Hello World! This is a complete test payload with binary data: \x00\xff\xfe" * 500
    app = make_mock_download_app(payload, filename="payload.bin")
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="https://public-cdn.example.com"
    ) as client:
        engine = HttpEngine(client=client, allow_local=True, chunk_size=256)
        task = Task(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            source_type="url",
            source_uri="https://public-cdn.example.com/files/download",
            name="payload.bin",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            dest = Path(tmp_dir)
            progresses = []
            async for p in engine.start(task=task, selected=[0], dest=dest):
                progresses.append(p)

            # Assert progress states
            assert len(progresses) > 0
            assert progresses[-1].state == "completed"
            assert progresses[-1].downloaded_bytes == len(payload)
            assert progresses[-1].total_bytes == len(payload)

            # Assert file created on disk with exact payload
            out_file = dest / "payload.bin"
            assert out_file.exists()
            assert out_file.read_bytes() == payload


@pytest.mark.asyncio
async def test_range_resume_after_being_killed_midway() -> None:
    """Verify an interrupted download resumes via Range header and produces complete file."""
    # 50,000 bytes test payload
    payload = bytes(i % 256 for i in range(50000))
    app = make_mock_download_app(payload, filename="large_dataset.bin")
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="https://public-cdn.example.com"
    ) as client:
        engine = HttpEngine(client=client, allow_local=True, chunk_size=512)
        task = Task(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            source_type="url",
            source_uri="https://public-cdn.example.com/files/download",
            name="large_dataset.bin",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            dest = Path(tmp_dir)
            out_file = dest / "large_dataset.bin"

            # 1. Start download and interrupt midway (simulating process crash / SIGKILL)
            bytes_before_interruption = 0
            gen1 = engine.start(task=task, selected=[0], dest=dest)
            try:
                async for p in gen1:
                    bytes_before_interruption = p.downloaded_bytes
                    if bytes_before_interruption >= 15000:
                        # Break out early to simulate killing download midway
                        break
            finally:
                await gen1.aclose()

            assert out_file.exists()
            partial_size = out_file.stat().st_size
            assert partial_size == bytes_before_interruption
            assert 15000 <= partial_size < len(payload)

            # 2. Resume download on the same destination directory
            resumed_progresses = []
            gen2 = engine.start(task=task, selected=[0], dest=dest)
            try:
                async for p in gen2:
                    resumed_progresses.append(p)
            finally:
                await gen2.aclose()

            # Assert resumption completed
            assert len(resumed_progresses) > 0
            final_progress = resumed_progresses[-1]
            assert final_progress.state == "completed"
            assert final_progress.downloaded_bytes == len(payload)
            assert final_progress.total_bytes == len(payload)

            # 3. Verify final file matches entire original payload byte-for-byte
            final_data = out_file.read_bytes()
            assert len(final_data) == len(payload)
            assert final_data == payload


@pytest.mark.asyncio
async def test_fetch_metadata_returns_name_and_size() -> None:
    """Verify fetch_metadata parses Content-Disposition filename and Content-Length."""
    payload = b"Sample metadata payload" * 100
    app = make_mock_download_app(payload, filename="report_2026.csv")
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="https://public-cdn.example.com"
    ) as client:
        engine = HttpEngine(client=client, allow_local=True)
        metadata = await engine.fetch_metadata("https://public-cdn.example.com/files/download")

        assert metadata.name == "report_2026.csv"
        assert metadata.total_size_bytes == len(payload)
        assert len(metadata.files) == 1
        assert metadata.files[0].path == "report_2026.csv"
        assert metadata.files[0].size_bytes == len(payload)


@pytest.mark.asyncio
async def test_cancel_active_download() -> None:
    """Verify calling cancel terminates the active download with state='cancelled'."""
    payload = b"Data chunk to test cancellation" * 2000
    app = make_mock_download_app(payload, filename="cancel_test.bin")
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="https://public-cdn.example.com"
    ) as client:
        engine = HttpEngine(client=client, allow_local=True, chunk_size=256)
        task_id = uuid.uuid4()
        task = Task(
            id=task_id,
            user_id=uuid.uuid4(),
            source_type="url",
            source_uri="https://public-cdn.example.com/files/download",
            name="cancel_test.bin",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            dest = Path(tmp_dir)
            cancelled_seen = False

            gen = engine.start(task=task, selected=[0], dest=dest)
            try:
                async for p in gen:
                    if p.downloaded_bytes >= 1000 and not cancelled_seen:
                        # Cancel task
                        await engine.cancel(str(task_id))
                    if p.state == "cancelled":
                        cancelled_seen = True
                        break
            finally:
                await gen.aclose()

            assert cancelled_seen
