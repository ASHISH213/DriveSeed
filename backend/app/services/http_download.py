"""HTTP download engine with Range resume, SSRF protection, and progress tracking."""

import asyncio
import email.message
import time
import urllib.parse
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import httpx

from app.core.ssrf import SSRFError, validate_url
from app.interfaces.download import DownloadEngine
from app.interfaces.types import Progress, TaskFileMetadata, TaskMetadata
from app.models.task import Task


class HttpDownloadError(Exception):
    """Exception raised when an HTTP download fails."""


class HttpEngine:
    """DownloadEngine implementation for direct HTTP and HTTPS URLs."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        allow_local: bool = False,
        dns_resolver: Callable[[str], Awaitable[list[str]]] | None = None,
        chunk_size: int = 65536,
        max_redirects: int = 10,
    ) -> None:
        self._client = client
        self.allow_local = allow_local
        self.dns_resolver = dns_resolver
        self.chunk_size = chunk_size
        self.max_redirects = max_redirects
        # Controls mapping: task_id -> {"paused": bool, "cancelled": bool}
        self._controls: dict[str, dict[str, bool]] = {}

    def _get_client(self) -> httpx.AsyncClient:
        """Return configured or transient httpx client."""
        return self._client or httpx.AsyncClient(timeout=30.0)

    @staticmethod
    def _extract_filename_from_headers(headers: httpx.Headers) -> str | None:
        """Extract filename from Content-Disposition header if present."""
        cd = headers.get("content-disposition")
        if not cd:
            return None
        msg = email.message.EmailMessage()
        msg["content-disposition"] = cd
        filename = msg.get_filename()
        return Path(filename).name if filename else None

    @staticmethod
    def _infer_filename(url: str, headers: httpx.Headers | None = None) -> str:
        """Infer clean filename from Content-Disposition or URL path."""
        if headers:
            from_header = HttpEngine._extract_filename_from_headers(headers)
            if from_header:
                return from_header

        parsed = urllib.parse.urlsplit(url)
        path_name = Path(parsed.path).name.strip()
        if path_name and path_name != "/":
            return path_name

        return "download.bin"

    async def _safe_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> tuple[httpx.Response, str]:
        """Execute request following redirects safely with SSRF validation on every hop."""
        client = self._get_client()
        current_url = url
        req_headers = dict(headers or {})

        for _ in range(self.max_redirects):
            await validate_url(
                current_url,
                allow_local=self.allow_local,
                dns_resolver=self.dns_resolver,
            )

            response = await client.request(
                method=method,
                url=current_url,
                headers=req_headers,
                follow_redirects=False,
            )

            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise HttpDownloadError("Redirect response missing Location header")
                current_url = urllib.parse.urljoin(current_url, location)
                continue

            return response, current_url

        raise HttpDownloadError(f"Exceeded maximum redirect limit of {self.max_redirects}")

    async def fetch_metadata(self, source: str) -> TaskMetadata:
        """Fetch remote file size and filename via HEAD or Range-scoped GET."""
        resp = None
        final_url = source
        try:
            # First try lightweight HEAD request
            resp, final_url = await self._safe_request("HEAD", source)
            if resp.status_code in (405, 501):
                # HEAD not allowed, fallback to GET with Range: bytes=0-0
                resp, final_url = await self._safe_request(
                    "GET", source, headers={"Range": "bytes=0-0"}
                )
        except SSRFError:
            raise
        except Exception:
            # Fallback to Range GET
            resp, final_url = await self._safe_request(
                "GET", source, headers={"Range": "bytes=0-0"}
            )

        if resp.status_code >= 400:
            raise HttpDownloadError(f"HTTP request failed with status code {resp.status_code}")

        # Determine total size
        total_size = 0
        content_range = resp.headers.get("content-range")
        if content_range and "/" in content_range:
            parts = content_range.split("/")
            if parts[-1].isdigit():
                total_size = int(parts[-1])

        if total_size == 0:
            cl = resp.headers.get("content-length")
            if cl and cl.isdigit():
                total_size = int(cl)

        filename = self._infer_filename(final_url, resp.headers)

        files = [
            TaskFileMetadata(
                index=0,
                path=filename,
                size_bytes=total_size,
            )
        ]
        return TaskMetadata(
            name=filename,
            files=files,
            total_size_bytes=total_size,
        )

    async def start(
        self,
        task: Task,
        selected: list[int],
        dest: Path,
    ) -> AsyncIterator[Progress]:
        """Download remote URL to destination directory supporting Range resume and cancellation."""
        task_id = str(task.id)
        self._controls[task_id] = {"paused": False, "cancelled": False}

        dest.mkdir(parents=True, exist_ok=True)
        filename = Path(task.name).name if task.name else self._infer_filename(task.source_uri)
        target_path = dest / filename

        existing_bytes = target_path.stat().st_size if target_path.exists() else 0
        client = self._get_client()

        # Follow redirects with SSRF check
        current_url = task.source_uri
        response = None
        open_stream = None

        try:
            for _ in range(self.max_redirects):
                await validate_url(
                    current_url,
                    allow_local=self.allow_local,
                    dns_resolver=self.dns_resolver,
                )

                req_headers: dict[str, str] = {}
                if existing_bytes > 0:
                    req_headers["Range"] = f"bytes={existing_bytes}-"

                stream_ctx = client.stream(
                    "GET",
                    current_url,
                    headers=req_headers,
                    follow_redirects=False,
                )
                res = await stream_ctx.__aenter__()

                if res.is_redirect:
                    location = res.headers.get("location")
                    await stream_ctx.__aexit__(None, None, None)
                    if not location:
                        raise HttpDownloadError("Redirect response missing Location header")
                    current_url = urllib.parse.urljoin(current_url, location)
                    continue

                response = res
                open_stream = stream_ctx
                break

            if not response or not open_stream:
                raise HttpDownloadError(f"Exceeded redirect limit of {self.max_redirects}")

            # Determine response mode and total size
            if response.status_code == 206:
                # Partial content: server accepted Range header
                file_mode = "ab"
                downloaded_bytes = existing_bytes

                content_range = response.headers.get("content-range")
                if (
                    content_range
                    and "/" in content_range
                    and content_range.split("/")[-1].isdigit()
                ):
                    total_bytes = int(content_range.split("/")[-1])
                elif "content-length" in response.headers:
                    total_bytes = existing_bytes + int(response.headers["content-length"])
                else:
                    total_bytes = existing_bytes
            elif response.status_code == 200:
                # Full content: range ignored or fresh start
                file_mode = "wb"
                downloaded_bytes = 0
                cl = response.headers.get("content-length")
                total_bytes = int(cl) if cl and cl.isdigit() else 0
            elif response.status_code == 416:
                # Range Not Satisfiable: file might already be complete
                if existing_bytes > 0:
                    yield Progress(
                        task_id=task_id,
                        downloaded_bytes=existing_bytes,
                        total_bytes=existing_bytes,
                        speed_bps=0.0,
                        state="completed",
                    )
                    return
                raise HttpDownloadError("HTTP 416 Range Not Satisfiable")
            else:
                raise HttpDownloadError(f"HTTP request failed with status {response.status_code}")

            # Stream chunks to target file
            start_time = time.monotonic()
            last_speed_time = start_time
            bytes_since_speed = 0
            speed_bps = 0.0

            with open(target_path, file_mode) as f:
                async for chunk in response.aiter_bytes(chunk_size=self.chunk_size):
                    control = self._controls.get(task_id, {})
                    if control.get("cancelled"):
                        yield Progress(
                            task_id=task_id,
                            downloaded_bytes=downloaded_bytes,
                            total_bytes=total_bytes,
                            speed_bps=0.0,
                            state="cancelled",
                        )
                        return

                    while control.get("paused"):
                        yield Progress(
                            task_id=task_id,
                            downloaded_bytes=downloaded_bytes,
                            total_bytes=total_bytes,
                            speed_bps=0.0,
                            state="paused",
                        )
                        await asyncio.sleep(0.1)
                        control = self._controls.get(task_id, {})
                        if control.get("cancelled"):
                            yield Progress(
                                task_id=task_id,
                                downloaded_bytes=downloaded_bytes,
                                total_bytes=total_bytes,
                                speed_bps=0.0,
                                state="cancelled",
                            )
                            return

                    f.write(chunk)
                    f.flush()
                    downloaded_bytes += len(chunk)
                    bytes_since_speed += len(chunk)

                    now = time.monotonic()
                    delta = now - last_speed_time
                    if delta >= 0.5:
                        speed_bps = bytes_since_speed / delta
                        bytes_since_speed = 0
                        last_speed_time = now

                    yield Progress(
                        task_id=task_id,
                        downloaded_bytes=downloaded_bytes,
                        total_bytes=max(total_bytes, downloaded_bytes),
                        speed_bps=speed_bps,
                        state="downloading",
                    )

            # Download finished successfully
            final_total = max(total_bytes, downloaded_bytes)
            yield Progress(
                task_id=task_id,
                downloaded_bytes=downloaded_bytes,
                total_bytes=final_total,
                speed_bps=0.0,
                state="completed",
            )

        finally:
            self._controls.pop(task_id, None)
            if open_stream:
                await open_stream.__aexit__(None, None, None)

    async def pause(self, task_id: str) -> None:
        """Signal an active task to pause."""
        if task_id in self._controls:
            self._controls[task_id]["paused"] = True

    async def resume(self, task_id: str) -> None:
        """Signal a paused task to resume."""
        if task_id in self._controls:
            self._controls[task_id]["paused"] = False

    async def cancel(self, task_id: str) -> None:
        """Signal an active task to cancel."""
        if task_id in self._controls:
            self._controls[task_id]["cancelled"] = True


# Static type verification of protocol adherence
_conforms: DownloadEngine = HttpEngine()
