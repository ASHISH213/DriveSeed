"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.events import router as events_router
from app.api.files import router as files_router
from app.api.tasks import router as tasks_router
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

    # Register API routers
    app.include_router(auth_router)
    app.include_router(tasks_router)
    app.include_router(events_router)
    app.include_router(files_router)

    dist_dir = (
        Path(app_settings.FRONTEND_DIST_DIR).resolve()
        if app_settings.FRONTEND_DIST_DIR
        else (Path(__file__).resolve().parent.parent.parent / "frontend" / "dist")
    )

    if dist_dir.is_dir() and (dist_dir / "index.html").is_file():
        assets_dir = dist_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> FileResponse:
            if full_path.startswith("api/") or full_path == "api":
                raise HTTPException(status_code=404, detail="Not Found")
            file_path = dist_dir / full_path
            if full_path and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(dist_dir / "index.html")

    return app


app = create_app()
