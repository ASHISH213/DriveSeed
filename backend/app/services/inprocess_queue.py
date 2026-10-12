"""In-process background TaskQueue implementation for Google Colab profile."""

import asyncio
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class InProcessQueue:
    """TaskQueue running jobs asynchronously within the same process without Redis."""

    def __init__(self) -> None:
        self._active_tasks: dict[str, asyncio.Task[Any]] = {}

    async def enqueue(self, name: str, **kwargs: Any) -> str:
        """Launch background task in-process and return job identifier."""
        job_id = f"job-{uuid.uuid4()}"

        if name == "process_download_task":
            from app.workers.pipeline import process_download_task

            task_id = kwargs.get("task_id")
            if not task_id:
                raise ValueError("Missing task_id argument for process_download_task")

            ctx: dict[str, Any] = {}
            coro = process_download_task(ctx=ctx, task_id=str(task_id))
            bg_task = asyncio.create_task(coro)
            self._active_tasks[job_id] = bg_task

            def _done_callback(t: asyncio.Task[Any]) -> None:
                self._active_tasks.pop(job_id, None)
                if t.cancelled():
                    logger.warning("InProcessQueue job %s cancelled", job_id)
                elif exc := t.exception():
                    logger.error("InProcessQueue job %s failed with exception: %s", job_id, exc)

            bg_task.add_done_callback(_done_callback)
            return job_id

        logger.warning("Unknown job type '%s' requested in InProcessQueue", name)
        return job_id
