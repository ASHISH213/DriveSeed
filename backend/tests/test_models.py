"""Unit tests for SQLAlchemy models."""

import uuid
from datetime import UTC, datetime

from app.models import Base, Task, User


def test_base_metadata_contains_tables() -> None:
    """Verify that Base metadata contains users and tasks tables."""
    table_names = Base.metadata.tables.keys()
    assert "users" in table_names
    assert "tasks" in table_names


def test_user_model_attributes() -> None:
    """Verify User model instance attributes and default values."""
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        google_sub="sub_12345",
        email="user@example.com",
        drive_refresh_token_enc="enc_token",
        drive_root_folder_id="root_folder_1",
        created_at=now,
    )

    assert user.id == user_id
    assert user.google_sub == "sub_12345"
    assert user.email == "user@example.com"
    assert user.drive_refresh_token_enc == "enc_token"
    assert user.drive_root_folder_id == "root_folder_1"
    assert user.created_at == now


def test_task_model_attributes() -> None:
    """Verify Task model instance attributes and default values."""
    task_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    task = Task(
        id=task_id,
        user_id=user_id,
        source_type="magnet",
        source_uri="magnet:?xt=urn:btih:example",
        info_hash="aabbccddeeff",
        name="Ubuntu Linux 24.04 ISO",
        state="queued",
        progress=0.0,
        size_bytes=2048000000,
        error=None,
        created_at=now,
    )

    assert task.id == task_id
    assert task.user_id == user_id
    assert task.source_type == "magnet"
    assert task.name == "Ubuntu Linux 24.04 ISO"
    assert task.state == "queued"
    assert task.progress == 0.0
    assert task.size_bytes == 2048000000
