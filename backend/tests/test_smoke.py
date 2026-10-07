"""Smoke tests for FastAPI application."""

from app.main import app


def test_app_version() -> None:
    """Verify application version."""
    assert app.version == "0.1.0"
