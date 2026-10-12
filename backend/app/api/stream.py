import mimetypes
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.rate_limit import StreamConcurrencyLimiter, get_stream_concurrency_limiter
from app.interfaces.streamer import Streamer
from app.models.task import Task
from app.models.user import User
from app.services.stream import MediaProxyDisabledError, ProxyStreamer
from app.services.torrent import get_torrent_engine
from app.services.transcode import HlsTranscodeService

router = APIRouter(tags=["Streaming"])


def get_streamer(settings: Annotated[Settings, Depends(get_settings)]) -> Streamer:
    """Dependency provider returning active Streamer instance for the profile."""
    if settings.PROFILE == "colab":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MEDIA_PROXY_DISABLED",
                    "message": "Media proxying is disabled in colab profile",
                }
            },
        )
    return ProxyStreamer(settings=settings)


@router.get("/stream/{file_id}")
@router.get("/api/stream/{file_id}")
async def stream_media(
    file_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    streamer: Annotated[Streamer, Depends(get_streamer)],
    stream_limiter: Annotated[StreamConcurrencyLimiter, Depends(get_stream_concurrency_limiter)],
) -> Response:
    """Stream stored audio/video files supporting 206 Partial Content range seeking."""
    await stream_limiter.acquire(user_id=str(current_user.id), file_id=file_id)

    range_header = request.headers.get("Range")

    try:
        stream_resp = await streamer.stream(
            user=current_user,
            file_id=file_id,
            range_header=range_header,
        )
        if stream_resp.status_code == 416:
            await stream_limiter.release(user_id=str(current_user.id), file_id=file_id)
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers=stream_resp.headers,
            )
    except FileNotFoundError:
        await stream_limiter.release(user_id=str(current_user.id), file_id=file_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"File with ID '{file_id}' was not found in storage",
                }
            },
        ) from None
    except MediaProxyDisabledError:
        await stream_limiter.release(user_id=str(current_user.id), file_id=file_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MEDIA_PROXY_DISABLED",
                    "message": "Media proxying is disabled in colab profile",
                }
            },
        ) from None
    except Exception:
        await stream_limiter.release(user_id=str(current_user.id), file_id=file_id)
        raise

    async def cleanup_iterator() -> AsyncIterator[bytes]:
        try:
            async for chunk in stream_resp.content_iterator:
                yield chunk
        finally:
            await stream_limiter.release(user_id=str(current_user.id), file_id=file_id)

    return StreamingResponse(
        content=cleanup_iterator(),
        status_code=stream_resp.status_code,
        headers=stream_resp.headers,
        media_type=stream_resp.headers.get("Content-Type", "application/octet-stream"),
    )


@router.get("/stream/{file_id}/handoff")
@router.get("/api/stream/{file_id}/handoff")
async def stream_handoff(
    file_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Redirect to Google Drive native viewer for Colab compliance."""
    from app.services.handoff_streamer import DriveHandoffStreamer

    streamer = DriveHandoffStreamer()
    resp = await streamer.stream(user=current_user, file_id=file_id, range_header=None)
    return RedirectResponse(
        url=resp.headers["Location"],
        status_code=resp.status_code,
        headers=resp.headers,
    )


def get_hls_service(settings: Annotated[Settings, Depends(get_settings)]) -> HlsTranscodeService:
    """Dependency provider returning active HlsTranscodeService instance."""
    if settings.PROFILE == "colab":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MEDIA_PROXY_DISABLED",
                    "message": "Media proxying and transcoding are disabled in colab profile",
                }
            },
        )
    return HlsTranscodeService(settings=settings)


@router.get("/hls/{file_id}/index.m3u8")
@router.get("/api/hls/{file_id}/index.m3u8")
async def get_hls_playlist(
    file_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    hls_service: Annotated[HlsTranscodeService, Depends(get_hls_service)],
) -> FileResponse:
    """Serve master HLS playlist generated via on-demand FFmpeg transcoding."""
    try:
        playlist_path = await hls_service.get_or_start_transcode(user=current_user, file_id=file_id)
        return FileResponse(
            path=playlist_path,
            media_type="application/vnd.apple.mpegurl",
            headers={
                "Content-Type": "application/vnd.apple.mpegurl",
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"File with ID '{file_id}' was not found in storage",
                }
            },
        ) from None
    except MediaProxyDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MEDIA_PROXY_DISABLED",
                    "message": "Media proxying and transcoding are disabled in colab profile",
                }
            },
        ) from None


@router.get("/hls/{file_id}/{segment_file}")
@router.get("/api/hls/{file_id}/{segment_file}")
async def get_hls_segment(
    file_id: str,
    segment_file: str,
    current_user: Annotated[User, Depends(get_current_user)],
    hls_service: Annotated[HlsTranscodeService, Depends(get_hls_service)],
) -> FileResponse:
    """Serve an individual HLS video transport stream (.ts) segment."""
    try:
        segment_path = await hls_service.get_segment_path(
            user=current_user, file_id=file_id, segment_name=segment_file
        )
        return FileResponse(
            path=segment_path,
            media_type="video/mp2t",
            headers={
                "Content-Type": "video/mp2t",
                "Cache-Control": "public, max-age=86400",
            },
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SEGMENT_NOT_FOUND",
                    "message": f"Segment '{segment_file}' was not found",
                }
            },
        ) from None
    except MediaProxyDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MEDIA_PROXY_DISABLED",
                    "message": "Media proxying and transcoding are disabled in colab profile",
                }
            },
        ) from None


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".avi",
    ".mov",
    ".flv",
    ".wmv",
    ".m4v",
    ".ts",
    ".mp3",
    ".aac",
    ".flac",
    ".ogg",
    ".m4a",
}


def _parse_task_range_header(range_header: str, file_size: int) -> tuple[int, int] | None:
    """Parse HTTP Range header for active task streaming returning (start, end) or None."""
    if not range_header or not range_header.startswith("bytes="):
        return None
    raw_range = range_header[len("bytes=") :].strip()
    if "-" not in raw_range:
        return None
    parts = raw_range.split("-", 1)
    try:
        if not parts[0]:
            suffix = int(parts[1])
            if suffix <= 0:
                return None
            start = max(0, file_size - suffix)
            end = file_size - 1
        elif not parts[1]:
            start = int(parts[0])
            end = file_size - 1
        else:
            start = int(parts[0])
            end = int(parts[1])
        return start, end
    except ValueError:
        return None


def verify_task_streaming_allowed(
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Verify that media proxying and streaming are permitted under the current profile."""
    if settings.PROFILE == "colab":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MEDIA_PROXY_DISABLED",
                    "message": "Media proxying is disabled in colab profile",
                }
            },
        )


@router.get("/stream/task/{task_id}")
@router.get("/api/stream/task/{task_id}")
async def stream_task_media(
    task_id: str,
    request: Request,
    _allowed: Annotated[None, Depends(verify_task_streaming_allowed)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    stream_limiter: Annotated[StreamConcurrencyLimiter, Depends(get_stream_concurrency_limiter)],
) -> Response:
    """Stream an actively downloading torrent or direct task directly from scratch disk."""

    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "TASK_NOT_FOUND",
                    "message": f"Task '{task_id}' not found",
                }
            },
        ) from None

    stmt = (
        select(Task)
        .where(Task.id == task_uuid, Task.user_id == current_user.id)
        .options(selectinload(Task.files))
    )
    res = await db.execute(stmt)
    task = res.scalars().first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "TASK_NOT_FOUND",
                    "message": f"Task '{task_id}' not found",
                }
            },
        )

    if task.state == "completed":
        for tf in task.files:
            if tf.drive_file_id:
                return RedirectResponse(
                    url=f"/stream/{tf.drive_file_id}",
                    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "TASK_COMPLETED",
                    "message": "Task already completed and temp files deleted",
                }
            },
        )

    if task.state in ("failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "TASK_INACTIVE",
                    "message": f"Task is in '{task.state}' state",
                }
            },
        )

    if task.state in ("queued", "fetching_metadata", "awaiting_selection"):
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail={
                "error": {
                    "code": "DOWNLOAD_NOT_STARTED",
                    "message": "Task download has not started yet",
                }
            },
        )

    # Trigger sequential piece download and boundary prioritization in torrent engine
    if task.source_type == "magnet":
        engine = get_torrent_engine(settings=settings)
        await engine.enable_sequential_download(str(task.id))

    # Locate media file in scratch disk directory
    task_dest = Path(settings.TEMP_DOWNLOAD_DIR) / str(task.id)
    if not task_dest.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SCRATCH_FILE_NOT_FOUND",
                    "message": "Download directory not found on scratch disk",
                }
            },
        )

    all_files = [f for f in task_dest.rglob("*") if f.is_file()]
    if not all_files:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail={
                "error": {
                    "code": "BUFFER_TOO_SMALL",
                    "message": "No data downloaded yet",
                }
            },
        )

    media_candidates = [f for f in all_files if f.suffix.lower() in VIDEO_EXTENSIONS]
    if media_candidates:
        target_file = max(media_candidates, key=lambda f: f.stat().st_size)
    else:
        target_file = max(all_files, key=lambda f: f.stat().st_size)

    current_size = target_file.stat().st_size
    if current_size < 1024:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail={
                "error": {
                    "code": "BUFFER_TOO_SMALL",
                    "message": "Download buffer too small to start streaming yet",
                }
            },
        )

    resource_id = f"task_{task.id}"
    await stream_limiter.acquire(user_id=str(current_user.id), file_id=resource_id)

    total_size = (
        task.size_bytes if (task.size_bytes and task.size_bytes > current_size) else current_size
    )
    mime_type, _ = mimetypes.guess_type(target_file.name)
    if not mime_type:
        mime_type = (
            "video/mp4" if target_file.suffix.lower() == ".mp4" else "application/octet-stream"
        )

    range_header = request.headers.get("Range")
    if range_header:
        parsed_range = _parse_task_range_header(range_header, current_size)
        if parsed_range is None or parsed_range[0] >= current_size:
            await stream_limiter.release(user_id=str(current_user.id), file_id=resource_id)
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={
                    "Content-Range": f"bytes */{current_size}",
                    "Accept-Ranges": "bytes",
                },
            )
        start, end = parsed_range
        end = min(end, current_size - 1)
        content_length = end - start + 1
        status_code = status.HTTP_206_PARTIAL_CONTENT
        headers = {
            "Content-Range": f"bytes {start}-{end}/{total_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": mime_type,
            "Cache-Control": "no-cache, no-store, must-revalidate",
        }
    else:
        start = 0
        end = current_size - 1
        content_length = current_size
        status_code = status.HTTP_200_OK
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": mime_type,
            "Cache-Control": "no-cache, no-store, must-revalidate",
        }

    async def file_chunk_generator(
        file_path: Path, start_byte: int, end_byte: int, chunk_size: int = 64 * 1024
    ) -> AsyncIterator[bytes]:
        bytes_to_read = end_byte - start_byte + 1
        bytes_read = 0
        with open(file_path, "rb") as f:
            f.seek(start_byte)
            while bytes_read < bytes_to_read:
                to_read = min(chunk_size, bytes_to_read - bytes_read)
                data = f.read(to_read)
                if not data:
                    break
                bytes_read += len(data)
                yield data

    async def cleanup_iterator() -> AsyncIterator[bytes]:
        try:
            async for chunk in file_chunk_generator(target_file, start, end):
                yield chunk
        finally:
            await stream_limiter.release(user_id=str(current_user.id), file_id=resource_id)

    return StreamingResponse(
        content=cleanup_iterator(),
        status_code=status_code,
        headers=headers,
        media_type=mime_type,
    )
