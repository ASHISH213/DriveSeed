"""Tests for health check endpoint and configuration."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app, create_app


@pytest.mark.asyncio
async def test_healthz_endpoint() -> None:
    """GET /healthz should return 200 and {'status': 'ok'}."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
