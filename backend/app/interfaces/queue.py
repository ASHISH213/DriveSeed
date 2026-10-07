"""TaskQueue protocol definition."""

from typing import Any, Protocol


class TaskQueue(Protocol):
    """Protocol for background job queue operations."""

    async def enqueue(self, name: str, **kwargs: Any) -> str:
        """Enqueue a background job with arguments and return the job identifier."""
        ...
