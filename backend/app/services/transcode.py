"""FFmpeg on-demand HLS transcoding service with concurrency controls and segment caching."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from fastapi import HTTPException, status

from app.core.config import Settings, get_settings
from app.interfaces.storage import StorageBackend
from app.models.user import User
from app.services.drive import DriveApiStorage
from app.services.stream import MediaProxyDisabledError

logger = logging.getLogger(__name__)


class TranscodeCapExceededError(HTTPException):
    """Raised when maximum concurrent on-demand transcodes are reached."""

    def __init__(self, max_concurrent: int) -> None:
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "transcode_cap_exceeded",
                    "message": (
                        f"Maximum concurrent transcoding limit ({max_concurrent}) reached. "
                        "Please wait for an active stream to complete or close other player tabs."
                    ),
                }
            },
        )


@dataclass
class TranscodeSession:
    """Represents an active or cached HLS transcoding session."""

    file_id: str
    user_id: str
    output_dir: Path
    created_at: float = field(default_factory=time.monotonic)
    last_accessed: float = field(default_factory=time.monotonic)
    process: asyncio.subprocess.Process | None = None
    is_complete: bool = False
    error: str | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def playlist_path(self) -> Path:
        return self.output_dir / "index.m3u8"


class HlsTranscodeService:
    """Orchestrates on-demand FFmpeg transcoding into HLS playlists and segments."""

    TRANSCODE_EXTENSIONS: ClassVar[set[str]] = {
        ".mkv",
        ".avi",
        ".flv",
        ".wmv",
        ".ts",
        ".vob",
        ".asf",
        ".mov",
        ".m4v",
        ".rmvb",
    }
    TRANSCODE_MIME_TYPES: ClassVar[set[str]] = {
        "video/x-matroska",
        "video/x-msvideo",
        "video/x-flv",
        "video/x-ms-wmv",
        "video/quicktime",
    }

    def __init__(
        self,
        settings: Settings | None = None,
        storage: StorageBackend | None = None,
        ffmpeg_bin: str = "ffmpeg",
    ) -> None:
        self.settings = settings or get_settings()
        self._storage = storage
        self.ffmpeg_bin = ffmpeg_bin
        self._sessions: dict[str, TranscodeSession] = {}
        self._lock = asyncio.Lock()

    def _get_storage(self) -> StorageBackend:
        if self._storage is not None:
            return self._storage
        return DriveApiStorage(settings=self.settings)

    def needs_transcoding(self, filename: str, mime_type: str | None = None) -> bool:
        """Determine whether a media file format requires on-demand transcoding."""
        lower_name = filename.lower()
        if any(lower_name.endswith(ext) for ext in self.TRANSCODE_EXTENSIONS):
            return True
        if mime_type and mime_type.lower() in self.TRANSCODE_MIME_TYPES:
            return True
        return False

    def _get_hls_base_dir(self) -> Path:
        base = Path(self.settings.TEMP_DOWNLOAD_DIR) / "hls"
        base.mkdir(parents=True, exist_ok=True)
        return base

    async def get_or_start_transcode(
        self,
        user: User,
        file_id: str,
        wait_timeout_seconds: float = 10.0,
    ) -> Path:
        """Start or retrieve an active HLS transcode session and wait for index.m3u8."""
        if self.settings.PROFILE == "colab":
            raise MediaProxyDisabledError(
                "Media proxying and transcoding are disabled in colab profile"
            )

        storage = self._get_storage()
        # Verify user has access to file
        await storage.get_file(user, file_id)

        session_key = f"{user.id}:{file_id}"

        async with self._lock:
            # 1. Check if session already exists
            session = self._sessions.get(session_key)
            if session:
                session.last_accessed = time.monotonic()
            else:
                # 2. Check concurrency limit
                active_count = sum(
                    1
                    for s in self._sessions.values()
                    if not s.is_complete and s.process and s.process.returncode is None
                )
                if active_count >= self.settings.MAX_CONCURRENT_TRANSCODES:
                    raise TranscodeCapExceededError(self.settings.MAX_CONCURRENT_TRANSCODES)

                out_dir = self._get_hls_base_dir() / file_id
                out_dir.mkdir(parents=True, exist_ok=True)

                session = TranscodeSession(
                    file_id=file_id,
                    user_id=str(user.id),
                    output_dir=out_dir,
                )
                self._sessions[session_key] = session
                # Spawn background transcoding task
                asyncio.create_task(self._run_ffmpeg(user, file_id, session))

        # 3. Wait for index.m3u8 with at least one segment
        deadline = time.monotonic() + wait_timeout_seconds
        while time.monotonic() < deadline:
            if session.playlist_path.exists() and session.playlist_path.stat().st_size > 0:
                content = session.playlist_path.read_text(encoding="utf-8", errors="ignore")
                if ".ts" in content:
                    return session.playlist_path

            if session.error:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"error": {"code": "transcode_failed", "message": session.error}},
                )

            if (
                session.process
                and session.process.returncode is not None
                and session.process.returncode != 0
            ):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error": {
                            "code": "transcode_failed",
                            "message": "FFmpeg process failed",
                        }
                    },
                )

            await asyncio.sleep(0.15)

        if session.playlist_path.exists() and session.playlist_path.stat().st_size > 0:
            return session.playlist_path

        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error": {
                    "code": "transcode_timeout",
                    "message": "Transcoder initialization timed out",
                }
            },
        )

    async def get_segment_path(
        self,
        user: User,
        file_id: str,
        segment_name: str,
        wait_timeout_seconds: float = 12.0,
    ) -> Path:
        """Locate an HLS segment, waiting if it is currently being encoded."""
        if self.settings.PROFILE == "colab":
            raise MediaProxyDisabledError(
                "Media proxying and transcoding are disabled in colab profile"
            )

        session_key = f"{user.id}:{file_id}"
        session = self._sessions.get(session_key)

        # Basic path traversal protection
        clean_name = os.path.basename(segment_name)
        if clean_name != segment_name or ".." in segment_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "invalid_segment", "message": "Invalid segment path"}},
            )

        segment_path = self._get_hls_base_dir() / file_id / clean_name

        if session:
            session.last_accessed = time.monotonic()

        deadline = time.monotonic() + wait_timeout_seconds
        while time.monotonic() < deadline:
            if segment_path.exists() and segment_path.stat().st_size > 0:
                return segment_path

            # If no active session or process finished and segment doesn't exist
            if not session or (session.is_complete and not segment_path.exists()):
                break

            await asyncio.sleep(0.15)

        if segment_path.exists():
            return segment_path

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "segment_not_found",
                    "message": f"Segment {clean_name} not found",
                }
            },
        )

    async def _run_ffmpeg(self, user: User, file_id: str, session: TranscodeSession) -> None:
        """Internal worker spooling input from storage to FFmpeg HLS encoding."""
        storage = self._get_storage()
        temp_src: Path | None = None

        try:
            # 1. Prepare input: Spool source stream from StorageBackend to a temporary local file
            src_dir = self._get_hls_base_dir() / f"src_{file_id}"
            src_dir.mkdir(parents=True, exist_ok=True)
            temp_src = src_dir / f"source_{file_id}.media"

            with open(temp_src, "wb") as f_out:
                async for chunk in storage.open_range(user, file_id, 0, None):
                    f_out.write(chunk)

            # 2. Build FFmpeg command line
            out_dir = session.output_dir
            segment_pattern = str(out_dir / "segment_%03d.ts")
            playlist_file = str(out_dir / "index.m3u8")

            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-i",
                str(temp_src),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-hls_time",
                str(self.settings.HLS_SEGMENT_DURATION_SECONDS),
                "-hls_list_size",
                "0",
                "-hls_segment_filename",
                segment_pattern,
                "-f",
                "hls",
                playlist_file,
            ]

            logger.info("Starting FFmpeg transcoding for file %s: %s", file_id, " ".join(cmd))

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            session.process = proc

            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                err_msg = stderr.decode(errors="replace")[-500:] if stderr else "Unknown error"
                session.error = err_msg
                logger.error("FFmpeg transcode failed for file %s: %s", file_id, err_msg)
            else:
                session.is_complete = True
                logger.info("FFmpeg transcode completed successfully for file %s", file_id)

        except Exception as exc:
            session.error = str(exc)
            logger.exception("Exception during FFmpeg transcoding for file %s: %s", file_id, exc)
        finally:
            if temp_src and temp_src.exists():
                try:
                    temp_src.unlink(missing_ok=True)
                    if temp_src.parent.exists():
                        shutil.rmtree(temp_src.parent, ignore_errors=True)
                except Exception:
                    pass

    def reset(self) -> None:
        """Clear all sessions and remove temp HLS files (for tests)."""
        for s in self._sessions.values():
            if s.process and s.process.returncode is None:
                try:
                    s.process.terminate()
                except Exception:
                    pass
        self._sessions.clear()
        base = Path(self.settings.TEMP_DOWNLOAD_DIR) / "hls"
        if base.exists():
            shutil.rmtree(base, ignore_errors=True)
