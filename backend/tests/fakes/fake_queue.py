"""In-memory fake implementation of TaskQueue for tests."""

import uuid
from typing import Any

from app.interfaces.queue import TaskQueue


class FakeTaskQueue:
    """In-memory task queue recording enqueued jobs."""

    def __init__(self) -> None:
        self.jobs: list[dict[str, Any]] = []

    async def enqueue(self, name: str, **kwargs: Any) -> str:
        """Record job call and return a generated job identifier."""
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        self.jobs.append(
            {
                "id": job_id,
                "name": name,
                "kwargs": kwargs,
            }
        )
        return job_id


# Type assertion for static protocol conformance
_conforms: TaskQueue = FakeTaskQueue()
