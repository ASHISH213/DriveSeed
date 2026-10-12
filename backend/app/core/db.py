"""Database connection and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import text

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create singleton SQLAlchemy async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = {}
        engine_kwargs: dict[str, object] = {
            "echo": settings.DEBUG,
        }
        if "sqlite" in settings.DATABASE_URL:
            connect_args["check_same_thread"] = False
        else:
            engine_kwargs["pool_pre_ping"] = True

        _engine = create_async_engine(
            settings.DATABASE_URL,
            connect_args=connect_args,
            **engine_kwargs,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create singleton async sessionmaker."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency yielding an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def check_db_connection() -> bool:
    """Execute a simple query to verify database connectivity."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def close_db_connection() -> None:
    """Dispose of the database engine on shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
