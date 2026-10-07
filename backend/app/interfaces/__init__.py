"""Interfaces package exposing protocol definitions and types."""

from app.interfaces.download import DownloadEngine
from app.interfaces.queue import TaskQueue
from app.interfaces.storage import StorageBackend
from app.interfaces.streamer import Streamer
from app.interfaces.types import (
    Progress,
    StorageQuota,
    StoredFile,
    StreamResponse,
    TaskFileMetadata,
    TaskMetadata,
)

__all__ = [
    "DownloadEngine",
    "Progress",
    "StorageBackend",
    "StorageQuota",
    "StoredFile",
    "StreamResponse",
    "Streamer",
    "TaskFileMetadata",
    "TaskMetadata",
    "TaskQueue",
]
