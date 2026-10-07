"""Smoke tests for project skeleton."""

from app.main import get_app_version


def test_get_app_version() -> None:
    """Verify smoke test passes and version is returned."""
    assert get_app_version() == "0.1.0"
