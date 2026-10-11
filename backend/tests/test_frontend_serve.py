"""Tests for static frontend bundle serving in FastAPI."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_static_bundle_not_configured(tmp_path: Path) -> None:
    """When frontend/dist does not exist, /healthz works and root returns 404."""
    non_existent = tmp_path / "does_not_exist"
    settings = Settings(FRONTEND_DIST_DIR=str(non_existent))
    app = create_app(settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Health check still works
        health_resp = await client.get("/healthz")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"

        # Root returns 404
        root_resp = await client.get("/")
        assert root_resp.status_code == 404


@pytest.mark.asyncio
async def test_static_bundle_serving_and_spa_fallback(tmp_path: Path) -> None:
    """When frontend bundle exists, index.html is served and SPA fallback works."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    index_file = dist_dir / "index.html"
    index_file.write_text("<!DOCTYPE html><html><body><div id='root'>DriveSeed</div></body></html>")

    assets_dir = dist_dir / "assets"
    assets_dir.mkdir()
    css_file = assets_dir / "main.css"
    css_file.write_text("body { background: black; }")

    settings = Settings(FRONTEND_DIST_DIR=str(dist_dir))
    app = create_app(settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # /healthz takes priority over SPA
        health_resp = await client.get("/healthz")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"

        # Root returns index.html
        root_resp = await client.get("/")
        assert root_resp.status_code == 200
        assert "<div id='root'>DriveSeed</div>" in root_resp.text

        # Assets route serves static file
        asset_resp = await client.get("/assets/main.css")
        assert asset_resp.status_code == 200
        assert "background: black" in asset_resp.text

        # SPA fallback route returns index.html
        spa_resp = await client.get("/library/some/deep/link")
        assert spa_resp.status_code == 200
        assert "<div id='root'>DriveSeed</div>" in spa_resp.text

        # API routes return 404 rather than index.html
        api_resp = await client.get("/api/unknown")
        assert api_resp.status_code == 404


@pytest.mark.asyncio
async def test_real_frontend_bundle_served_when_built() -> None:
    """When frontend/dist is built, create_app() serves DriveSeed index."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health_resp = await client.get("/healthz")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"

        root_resp = await client.get("/")
        assert root_resp.status_code == 200
        assert "<title>DriveSeed</title>" in root_resp.text
        assert '<div id="root">' in root_resp.text
