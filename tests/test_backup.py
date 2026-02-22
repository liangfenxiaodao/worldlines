"""Tests for database backup and retention."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from worldlines.config import Config
from worldlines.jobs import run_backup
from worldlines.storage.schema import init_db


def _make_config(tmp_path, **overrides) -> Config:
    db_path = str(tmp_path / "test.db")
    backup_dir = str(tmp_path / "backups")
    defaults = {
        "database_path": db_path,
        "llm_api_key": "test-key",
        "llm_model": "test-model",
        "telegram_bot_token": "test-token",
        "telegram_chat_id": "test-chat",
        "backup_dir": backup_dir,
        "backup_retention_days": 7,
    }
    defaults.update(overrides)
    return Config(**defaults)


class TestRunBackup:
    def test_creates_backup_file(self, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with patch("worldlines.jobs._send_alert"):
            run_backup(config)

        backup_dir = Path(config.backup_dir)
        backups = list(backup_dir.glob("worldlines-*.db"))
        assert len(backups) == 1

        # Verify the backup is a valid SQLite database
        conn = sqlite3.connect(str(backups[0]))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        table_names = [t[0] for t in tables]
        assert "items" in table_names
        assert "analyses" in table_names

    def test_backup_filename_format(self, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with patch("worldlines.jobs._send_alert"):
            run_backup(config)

        backup_dir = Path(config.backup_dir)
        backups = list(backup_dir.glob("worldlines-*.db"))
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert backups[0].name == f"worldlines-{today}.db"

    def test_retention_removes_old_backups(self, tmp_path):
        config = _make_config(tmp_path, backup_retention_days=3)
        init_db(config.database_path)

        backup_dir = Path(config.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Create fake old backups with old mtimes
        old_backup = backup_dir / "worldlines-2020-01-01.db"
        old_backup.write_text("fake")
        # Set mtime to 30 days ago
        old_time = time.time() - (30 * 86400)
        import os
        os.utime(str(old_backup), (old_time, old_time))

        with patch("worldlines.jobs._send_alert"):
            run_backup(config)

        # Old backup should be removed
        assert not old_backup.exists()
        # New backup should exist
        remaining = list(backup_dir.glob("worldlines-*.db"))
        assert len(remaining) == 1

    def test_retention_keeps_recent_backups(self, tmp_path):
        config = _make_config(tmp_path, backup_retention_days=30)
        init_db(config.database_path)

        backup_dir = Path(config.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Create a recent backup
        recent_backup = backup_dir / "worldlines-recent.db"
        recent_backup.write_text("fake")

        with patch("worldlines.jobs._send_alert"):
            run_backup(config)

        # Recent backup should still exist
        assert recent_backup.exists()

    def test_records_pipeline_run(self, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with patch("worldlines.jobs._send_alert"):
            run_backup(config)

        from worldlines.storage.connection import get_connection
        with get_connection(config.database_path) as conn:
            row = conn.execute(
                "SELECT run_type, status FROM pipeline_runs WHERE run_type = 'backup'"
            ).fetchone()
        assert row is not None
        assert row["run_type"] == "backup"
        assert row["status"] == "success"

    def test_creates_backup_dir_if_missing(self, tmp_path):
        backup_dir = str(tmp_path / "nested" / "backups")
        config = _make_config(tmp_path, backup_dir=backup_dir)
        init_db(config.database_path)

        with patch("worldlines.jobs._send_alert"):
            run_backup(config)

        assert Path(backup_dir).is_dir()
        backups = list(Path(backup_dir).glob("worldlines-*.db"))
        assert len(backups) == 1

    def test_alerts_on_failure(self, tmp_path):
        config = _make_config(tmp_path, database_path="/nonexistent/db.sqlite")

        with patch("worldlines.jobs._send_alert") as mock_alert, \
             patch("worldlines.jobs._record_run"):
            run_backup(config)
            mock_alert.assert_called_once()
            assert "backup failed" in mock_alert.call_args[0][1].lower()
