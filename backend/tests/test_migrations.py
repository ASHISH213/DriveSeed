"""Tests for Alembic migrations."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migration_scripts_exist() -> None:
    """Verify that Alembic locates migration revisions."""
    base_dir = Path(__file__).resolve().parent.parent
    ini_path = base_dir / "alembic.ini"

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(base_dir / "migrations"))

    script = ScriptDirectory.from_config(cfg)
    revisions = list(script.walk_revisions())

    assert len(revisions) >= 1
    revisions_ids = [rev.revision for rev in revisions]
    assert "20261007_01" in revisions_ids
    assert "20261011_02" in revisions_ids
    assert "20261012_03" in revisions_ids
    assert "20261012_04" in revisions_ids
    assert "20261012_05" in revisions_ids
    assert "20261012_06" in revisions_ids
    assert "20261013_07" in revisions_ids


def test_migration_sql_generation_offline(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that alembic upgrade head --sql generates valid DDL."""
    base_dir = Path(__file__).resolve().parent.parent
    ini_path = base_dir / "alembic.ini"

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(base_dir / "migrations"))

    command.upgrade(cfg, "head", sql=True)
    captured = capsys.readouterr()
    sql_text = captured.out

    assert "CREATE TABLE users" in sql_text
    assert "CREATE TABLE tasks" in sql_text
    assert "CREATE TABLE task_files" in sql_text
    assert "CREATE TABLE api_tokens" in sql_text
    assert "CREATE TABLE webhook_endpoints" in sql_text
    assert "CREATE TABLE rss_subscriptions" in sql_text
    assert "CREATE TABLE rss_feed_items" in sql_text
    assert "FOREIGN KEY(user_id) REFERENCES users (id)" in sql_text
    assert "FOREIGN KEY(task_id) REFERENCES tasks (id)" in sql_text
    assert "telegram_chat_id" in sql_text
