"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.db import check_db_connection, close_db_connection
from app.core.redis import check_redis_connection, close_redis_connection
from app.schemas.health import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycles."""
    # Startup actions can be added here
    yield
    # Shutdown actions
    await close_db_connection()
    await close_redis_connection()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app_settings = settings or get_settings()

    app = FastAPI(
        title="DriveSeed",
        version="0.1.0",
        debug=app_settings.DEBUG,
        lifespan=lifespan,
    )

    if app_settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/healthz", response_model=HealthResponse, tags=["Health"])
    async def health_check(
        check_services: bool = Query(default=False, description="Verify database and Redis"),
    ) -> HealthResponse:
        """Health check endpoint with optional dependency verification."""
        if not check_services:
            return HealthResponse(status="ok")

        db_ok = await check_db_connection()
        redis_ok = await check_redis_connection()

        return HealthResponse(
            status="ok" if (db_ok and redis_ok) else "degraded",
            database="connected" if db_ok else "disconnected",
            redis="connected" if redis_ok else "disconnected",
        )

    return app


app = create_app()
