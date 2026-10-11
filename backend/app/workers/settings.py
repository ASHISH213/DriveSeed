"""Worker configuration and startup/shutdown lifecycle hooks for arq."""

from typing import Any

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.db import close_db_connection, get_session_factory
from app.workers.pipeline import process_download_task


async def startup(ctx: dict[str, Any]) -> None:
    """Initialize database and application configuration on worker startup."""
    settings = get_settings()
    ctx["settings"] = settings
    ctx["db_session_factory"] = get_session_factory()


async def shutdown(ctx: dict[str, Any]) -> None:
    """Close active database connections on worker shutdown."""
    await close_db_connection()


class WorkerSettings:
    """Configuration class for arq worker process."""

    functions = [process_download_task]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().REDIS_URL)
    max_jobs = 10
    job_timeout = 3600
