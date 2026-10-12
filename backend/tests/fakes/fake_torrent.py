"""In-memory fake implementation of libtorrent session and handle for testing."""

from dataclasses import dataclass
from typing import Any


@dataclass
class FakeFileInfo:
    """Mock file descriptor for FakeFileStorage."""

    path: str
    size_bytes: int


class FakeFileStorage:
    """Mock libtorrent file_storage."""

    def __init__(self, files: list[FakeFileInfo]) -> None:
        self._files = files

    def num_files(self) -> int:
        return len(self._files)

    def file_path(self, index: int) -> str:
        return self._files[index].path

    def file_size(self, index: int) -> int:
        return self._files[index].size_bytes


class FakeTorrentInfo:
    """Mock libtorrent torrent_info."""

    def __init__(self, name: str, files: list[FakeFileInfo]) -> None:
        self._name = name
        self._files = files
        self._storage = FakeFileStorage(files)

    def name(self) -> str:
        return self._name

    def total_size(self) -> int:
        return sum(f.size_bytes for f in self._files)

    def num_files(self) -> int:
        return len(self._files)

    def num_pieces(self) -> int:
        return max(1, self.total_size() // (1024 * 1024))

    def files(self) -> FakeFileStorage:
        return self._storage


class FakeTorrentStatus:
    """Mock libtorrent torrent_status."""

    def __init__(
        self,
        has_metadata: bool = True,
        is_seeding: bool = False,
        progress: float = 0.0,
        download_rate: int = 100000,
        total_done: int = 0,
        total_wanted: int = 100000,
        paused: bool = False,
    ) -> None:
        self.has_metadata = has_metadata
        self.is_seeding = is_seeding
        self.progress = progress
        self.download_rate = download_rate
        self.total_done = total_done
        self.total_wanted = total_wanted
        self.paused = paused
        self.state = 5  # seeding


class FakeTorrentHandle:
    """Mock libtorrent torrent_handle."""

    def __init__(
        self,
        name: str = "Ubuntu-24.04-desktop.iso",
        files: list[FakeFileInfo] | None = None,
        auto_complete_step: int = 4,
    ) -> None:
        self._files = files or [
            FakeFileInfo(path="Ubuntu-24.04-desktop.iso", size_bytes=1024 * 1024 * 20),
            FakeFileInfo(path="checksums.txt", size_bytes=1024),
        ]
        self._ti = FakeTorrentInfo(name=name, files=self._files)
        self._status = FakeTorrentStatus(
            has_metadata=True,
            total_wanted=self._ti.total_size(),
        )
        self.priorities: list[int] = [1] * len(self._files)
        self.step_count = 0
        self.auto_complete_step = auto_complete_step
        self.sequential_download: bool = False
        self.piece_priorities: dict[int, int] = {}

    def status(self) -> FakeTorrentStatus:
        self.step_count += 1
        if self.step_count >= self.auto_complete_step and not self._status.paused:
            self._status.total_done = self._status.total_wanted
            self._status.progress = 1.0
            self._status.is_seeding = True
        elif not self._status.paused:
            self._status.total_done = min(self._ti.total_size() // 2, 50000)
            self._status.progress = 0.5
            self._status.is_seeding = False
        return self._status

    def torrent_file(self) -> FakeTorrentInfo:
        return self._ti

    def prioritize_files(self, priorities: list[int]) -> None:
        self.priorities = list(priorities)

    def set_sequential_download(self, val: bool) -> None:
        self.sequential_download = val

    def piece_priority(self, piece: int, priority: int) -> None:
        self.piece_priorities[piece] = priority

    def pause(self) -> None:
        self._status.paused = True

    def resume(self) -> None:
        self._status.paused = False


class FakeTorrentSession:
    """Mock libtorrent session."""

    def __init__(self, auto_complete_step: int = 4) -> None:
        self.handles: list[FakeTorrentHandle] = []
        self.removed_handles: list[FakeTorrentHandle] = []
        self.auto_complete_step = auto_complete_step

    def add_torrent(self, params: Any) -> FakeTorrentHandle:
        handle = FakeTorrentHandle(auto_complete_step=self.auto_complete_step)
        self.handles.append(handle)
        return handle

    def remove_torrent(self, handle: Any) -> None:
        if handle in self.handles:
            self.handles.remove(handle)
        self.removed_handles.append(handle)
