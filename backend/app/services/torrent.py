"""Torrent download engine wrapping python-libtorrent with profile and priority support."""

import asyncio
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.interfaces.download import DownloadEngine
from app.interfaces.types import Progress, TaskFileMetadata, TaskMetadata
from app.models.task import Task


class TorrentEngineDisabledError(RuntimeError):
    """Exception raised when torrent engine operations are attempted under disabled profiles."""


class TorrentError(Exception):
    """Generic domain exception for torrent operations."""


class TorrentEngine:
    """DownloadEngine implementation using libtorrent bindings with Colab profile guard."""

    def __init__(
        self,
        settings: Settings | None = None,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._check_profile()

        self._session_factory = session_factory
        self._session: Any = None
        self._handles: dict[str, Any] = {}
        self._cancelled: set[str] = set()

    def _check_profile(self) -> None:
        """Enforce hard rule: TorrentEngine is strictly prohibited under PROFILE=colab."""
        if getattr(self.settings, "PROFILE", "server") == "colab":
            raise TorrentEngineDisabledError(
                "Torrent engine is strictly disabled when running with PROFILE=colab."
            )

    def _get_session(self) -> Any:
        """Return initialized or existing libtorrent session."""
        self._check_profile()
        if self._session is None:
            if self._session_factory:
                self._session = self._session_factory()
            else:
                import libtorrent as lt

                session_settings = {
                    "listen_interfaces": "0.0.0.0:6881,[::]:6881",
                    "alert_mask": (
                        lt.alert.category_t.error_notification
                        | lt.alert.category_t.status_notification
                    ),
                    "enable_dht": True,
                    "enable_lsd": True,
                    "enable_upnp": True,
                    "enable_natpmp": True,
                }
                self._session = lt.session(session_settings)  # type: ignore[call-overload]
        return self._session

    async def fetch_metadata(self, source: str, timeout_seconds: float = 30.0) -> TaskMetadata:
        """Fetch metadata including name and file listing from a magnet URI or torrent file."""
        self._check_profile()
        session = self._get_session()

        # Handle magnet link or torrent file path
        if hasattr(session, "add_torrent") and hasattr(session, "remove_torrent"):
            # Check if this is a fake session or real libtorrent
            try:
                import libtorrent as lt

                is_real_libtorrent = isinstance(session, lt.session)
            except ImportError:
                is_real_libtorrent = False

            if is_real_libtorrent:
                params = lt.parse_magnet_uri(source)
                # Paused temporary handle just for metadata inspection
                params.flags |= lt.torrent_flags.paused
                params.save_path = "."
                handle = session.add_torrent(params)
            else:
                handle = session.add_torrent(source)
        else:
            raise TorrentError("Unsupported torrent session configuration")

        try:
            start_time = asyncio.get_running_loop().time()
            while not handle.status().has_metadata:
                if (asyncio.get_running_loop().time() - start_time) > timeout_seconds:
                    raise TorrentError("Timed out waiting to fetch torrent metadata")
                await asyncio.sleep(0.2)

            ti = handle.torrent_file()
            files_storage = ti.files()
            files: list[TaskFileMetadata] = []

            for i in range(files_storage.num_files()):
                files.append(
                    TaskFileMetadata(
                        index=i,
                        path=files_storage.file_path(i),
                        size_bytes=files_storage.file_size(i),
                    )
                )

            return TaskMetadata(
                name=ti.name(),
                files=files,
                total_size_bytes=ti.total_size(),
            )
        finally:
            session.remove_torrent(handle)

    async def start(
        self,
        task: Task,
        selected: list[int],
        dest: Path,
    ) -> AsyncIterator[Progress]:
        """Start downloading torrent files with selective file prioritization."""
        self._check_profile()
        task_id = str(task.id)
        self._cancelled.discard(task_id)

        dest.mkdir(parents=True, exist_ok=True)
        session = self._get_session()

        try:
            import libtorrent as lt

            is_real = isinstance(session, lt.session)
        except ImportError:
            is_real = False

        if is_real:
            params = lt.parse_magnet_uri(task.source_uri)
            params.save_path = str(dest)
            handle = session.add_torrent(params)
        else:
            handle = session.add_torrent(task.source_uri)

        self._handles[task_id] = handle

        try:
            # 1. Wait for metadata if not present
            while not handle.status().has_metadata:
                if task_id in self._cancelled:
                    yield Progress(
                        task_id=task_id,
                        downloaded_bytes=0,
                        total_bytes=0,
                        speed_bps=0.0,
                        state="cancelled",
                    )
                    return

                yield Progress(
                    task_id=task_id,
                    downloaded_bytes=0,
                    total_bytes=0,
                    speed_bps=0.0,
                    state="fetching_metadata",
                )
                await asyncio.sleep(0.3)

            # 2. Configure file priorities if selection specified
            ti = handle.torrent_file()
            num_files = ti.num_files()
            if selected:
                priorities = [0] * num_files
                for idx in selected:
                    if 0 <= idx < num_files:
                        priorities[idx] = 1
                handle.prioritize_files(priorities)

            # 3. Stream download progress
            while True:
                status = handle.status()

                if task_id in self._cancelled:
                    handle.pause()
                    yield Progress(
                        task_id=task_id,
                        downloaded_bytes=status.total_done,
                        total_bytes=status.total_wanted,
                        speed_bps=0.0,
                        state="cancelled",
                    )
                    return

                is_complete = bool(
                    status.is_seeding
                    or (status.total_wanted > 0 and status.total_done >= status.total_wanted)
                )

                state_label = (
                    "completed" if is_complete else ("paused" if status.paused else "downloading")
                )

                yield Progress(
                    task_id=task_id,
                    downloaded_bytes=status.total_done,
                    total_bytes=status.total_wanted
                    if status.total_wanted > 0
                    else status.total_done,
                    speed_bps=float(status.download_rate),
                    state=state_label,
                )

                if is_complete:
                    break

                await asyncio.sleep(0.2)

        finally:
            self._handles.pop(task_id, None)

    async def pause(self, task_id: str) -> None:
        """Pause the active torrent handle."""
        self._check_profile()
        handle = self._handles.get(task_id)
        if handle:
            handle.pause()

    async def resume(self, task_id: str) -> None:
        """Resume the paused torrent handle."""
        self._check_profile()
        handle = self._handles.get(task_id)
        if handle:
            handle.resume()

    async def cancel(self, task_id: str) -> None:
        """Cancel the active torrent download."""
        self._check_profile()
        self._cancelled.add(task_id)
        handle = self._handles.get(task_id)
        if handle and self._session:
            self._session.remove_torrent(handle)


# Type assertion for static protocol conformance
_conforms: DownloadEngine = TorrentEngine()
