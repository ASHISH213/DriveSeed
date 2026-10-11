"""Background task queue implementation using arq and Redis."""

from typing import Any

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.core.config import Settings, get_settings
from app.interfaces.queue import TaskQueue


class ArqTaskQueue:
    """TaskQueue protocol implementation wrapping arq Redis client."""

    def __init__(
        self,
        pool: ArqRedis | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._pool = pool
        self._settings = settings or get_settings()

    async def get_pool(self) -> ArqRedis:
        """Get or create cached arq Redis pool connection."""
        if self._pool is None:
            redis_settings = RedisSettings.from_dsn(self._settings.REDIS_URL)
            self._pool = await create_pool(redis_settings)
        return self._pool

    async def enqueue(self, name: str, **kwargs: Any) -> str:
        """Enqueue a background task by function name."""
        pool = await self.get_pool()
        job = await pool.enqueue_job(name, **kwargs)
        if job is None:
            raise RuntimeError(f"Failed to enqueue job '{name}'")
        return str(job.job_id)


# Static type verification of protocol adherence
_conforms: TaskQueue = ArqTaskQueue()
