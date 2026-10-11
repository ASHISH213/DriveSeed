"""Pydantic schemas for Tasks and TaskFiles."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TaskCreateRequest(BaseModel):
    """Payload to submit a new download task."""

    source_uri: str = Field(..., description="Magnet URI or direct HTTP/HTTPS download link")
    name: str | None = Field(default=None, description="Optional custom name for the task")


class TaskFileResponse(BaseModel):
    """File item inside a task."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    path: str
    size_bytes: int
    selected: bool
    state: str
    drive_file_id: str | None = None


class TaskResponse(BaseModel):
    """Task details including state, progress, and file listing."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    source_type: Literal["magnet", "url"]
    source_uri: str
    info_hash: str | None = None
    name: str
    state: str
    progress: float
    size_bytes: int | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    files: list[TaskFileResponse] = Field(default_factory=list)


class TaskActionResponse(BaseModel):
    """Summary response following a task lifecycle action (pause, resume, cancel)."""

    id: uuid.UUID
    state: str
    message: str
