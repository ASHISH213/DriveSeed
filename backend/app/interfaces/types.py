"""Data structures and value objects for interface contracts."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from pydantic import BaseModel


class StoredFile(BaseModel):
    """Metadata describing a file stored in the storage backend."""

    id: str
    name: str
    parent_id: str
    mime_type: str
    size_bytes: int
    md5: str | None = None


class StorageQuota(BaseModel):
    """Storage quota metrics."""

    used_bytes: int
    total_bytes: int


class TaskFileMetadata(BaseModel):
    """Metadata for an individual file within a downloadable task."""

    index: int
    path: str
    size_bytes: int


class TaskMetadata(BaseModel):
    """Aggregated metadata for a downloadable source."""

    name: str
    files: list[TaskFileMetadata]
    total_size_bytes: int


class Progress(BaseModel):
    """Download task execution progress."""

    task_id: str
    downloaded_bytes: int
    total_bytes: int
    speed_bps: float
    state: str


@dataclass
class StreamResponse:
    """Streaming response bundle containing byte generator and HTTP metadata."""

    content_iterator: AsyncIterator[bytes]
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
