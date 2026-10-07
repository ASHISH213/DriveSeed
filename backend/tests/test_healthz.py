"""Tests for health check endpoint, configuration, and service connectivity."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.db import check_db_connection
from app.core.redis import check_redis_connection
from app.main import app, create_app


@pytest.mark.asyncio
async def test_healthz_endpoint() -> None:
    """GET /healthz should return 200 and {'status': 'ok'}."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_healthz_with_services_connected() -> None:
    """GET /healthz?check_services=true should report connected services."""
    with (
        patch("app.main.check_db_connection", new_callable=AsyncMock) as mock_db,
        patch("app.main.check_redis_connection", new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = True
        mock_redis.return_value = True

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/healthz?check_services=true")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["redis"] == "connected"


@pytest.mark.asyncio
async def test_healthz_with_service_degraded() -> None:
    """GET /healthz?check_services=true should report degraded if a service is down."""
    with (
        patch("app.main.check_db_connection", new_callable=AsyncMock) as mock_db,
        patch("app.main.check_redis_connection", new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = False
        mock_redis.return_value = True

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/healthz?check_services=true")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "disconnected"
    assert data["redis"] == "connected"


@pytest.mark.asyncio
async def test_check_db_connection_handles_failure() -> None:
    """check_db_connection returns False when database is unreachable."""
    with patch("app.core.db.get_engine") as mock_engine:
        mock_engine.side_effect = RuntimeError("DB unreachable")
        assert await check_db_connection() is False


@pytest.mark.asyncio
async def test_check_redis_connection_handles_failure() -> None:
    """check_redis_connection returns False when Redis is unreachable."""
    with patch("app.core.redis.get_redis_client") as mock_redis:
        mock_redis.side_effect = ConnectionError("Redis unreachable")
        assert await check_redis_connection() is False


def test_settings_profile_and_defaults() -> None:
    """Settings should load default server profile and configuration."""
    settings = Settings()
    assert settings.PROFILE == "server"
    assert settings.PORT == 8000
    assert "http://localhost:5173" in settings.CORS_ORIGINS


def test_settings_profile_override() -> None:
    """Settings should allow PROFILE=colab override."""
    settings = Settings(PROFILE="colab")
    assert settings.PROFILE == "colab"
    colab_app = create_app(settings=settings)
    assert colab_app.title == "DriveSeed"
