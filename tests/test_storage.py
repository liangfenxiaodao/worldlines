"""Tests for worldlines.storage — schema, connection, and constraints."""

from __future__ import annotations

import sqlite3

import pytest

from worldlines.storage.connection import get_connection
from worldlines.storage.schema import init_db

EXPECTED_TABLES = {"items", "analyses", "exposures", "deduplication_records", "digests", "adapter_state", "temporal_links", "pipeline_runs", "analysis_errors"}

EXPECTED_INDEXES = {
    "idx_items_timestamp",
    "idx_items_source_type",
    "idx_items_ingested_at",
    "idx_analyses_item_id",
    "idx_analyses_change_type",
    "idx_analyses_importance",
    "idx_analyses_analyzed_at",
    "idx_analyses_analysis_version",
    "idx_exposures_analysis_id",
    "idx_dedup_canonical_item_id",
    "idx_digests_sent_at",
    "idx_temporal_links_source_item_id",
    "idx_temporal_links_target_item_id",
    "idx_temporal_links_link_type",
    "idx_pipeline_runs_started_at",
    "idx_pipeline_runs_run_type",
}


@pytest.fixture()
def db_path(tmp_path):
    """Return a database path inside a temporary directory."""
    return str(tmp_path / "test.db")


@pytest.fixture()
def initialized_db(db_path):
    """Initialize the database and return the path."""
    init_db(db_path)
    return db_path


def _insert_item(conn: sqlite3.Connection, *, item_id: str = "item-1", dedup_hash: str = "hash-1") -> None:
    """Insert a minimal valid item row."""
    conn.execute(
        "INSERT INTO items (id, title, source_name, source_type, timestamp, content, ingested_at, dedup_hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (item_id, "Title", "Source", "news", "2025-01-01T00:00:00Z", "Content", "2025-01-01T00:00:00Z", dedup_hash),
    )


# --- Table and index existence ---


def test_init_db_creates_all_tables(initialized_db):
    with get_connection(initialized_db) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        table_names = {row["name"] for row in rows}
    assert EXPECTED_TABLES == table_names


def test_init_db_is_idempotent(db_path):
    init_db(db_path)
    init_db(db_path)  # Should not raise


def test_init_db_creates_indexes(initialized_db):
    with get_connection(initialized_db) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'").fetchall()
        index_names = {row["name"] for row in rows}
    assert EXPECTED_INDEXES == index_names


# --- Pragmas ---


def test_wal_mode_enabled(initialized_db):
    with get_connection(initialized_db) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"


def test_foreign_keys_enabled(initialized_db):
    with get_connection(initialized_db) as conn:
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


# --- Constraint enforcement ---


def test_foreign_key_enforcement(initialized_db):
    with pytest.raises(sqlite3.IntegrityError):
        with get_connection(initialized_db) as conn:
            conn.execute(
                "INSERT INTO analyses "
                "(id, item_id, dimensions, change_type, time_horizon, summary, importance, key_entities, analyzed_at, analysis_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("a-1", "nonexistent-item", "[]", "reinforcing", "short_term", "s", "low", "[]", "2025-01-01T00:00:00Z", "v1"),
            )


def test_dedup_hash_unique_constraint(initialized_db):
    with pytest.raises(sqlite3.IntegrityError):
        with get_connection(initialized_db) as conn:
            _insert_item(conn, item_id="item-1", dedup_hash="same-hash")
            _insert_item(conn, item_id="item-2", dedup_hash="same-hash")


def test_digest_date_unique_constraint(initialized_db):
    with pytest.raises(sqlite3.IntegrityError):
        with get_connection(initialized_db) as conn:
            conn.execute(
                "INSERT INTO digests "
                "(id, digest_date, item_count, dimension_breakdown, change_type_distribution, "
                "high_importance_items, summary_en, summary_zh, message_text, sent_at, telegram_message_ids) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("d-1", "2025-01-01", 5, "{}", "{}", "[]", None, None, "text", "2025-01-01T18:00:00Z", "[]"),
            )
            conn.execute(
                "INSERT INTO digests "
                "(id, digest_date, item_count, dimension_breakdown, change_type_distribution, "
                "high_importance_items, summary_en, summary_zh, message_text, sent_at, telegram_message_ids) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("d-2", "2025-01-01", 3, "{}", "{}", "[]", None, None, "text2", "2025-01-01T18:00:01Z", "[]"),
            )


def test_check_constraint_source_type(initialized_db):
    with pytest.raises(sqlite3.IntegrityError):
        with get_connection(initialized_db) as conn:
            conn.execute(
                "INSERT INTO items (id, title, source_name, source_type, timestamp, content, ingested_at, dedup_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("item-bad", "T", "S", "invalid_type", "2025-01-01T00:00:00Z", "C", "2025-01-01T00:00:00Z", "h"),
            )


def test_check_constraint_change_type(initialized_db):
    with pytest.raises(sqlite3.IntegrityError):
        with get_connection(initialized_db) as conn:
            _insert_item(conn)
            conn.execute(
                "INSERT INTO analyses "
                "(id, item_id, dimensions, change_type, time_horizon, summary, importance, key_entities, analyzed_at, analysis_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("a-1", "item-1", "[]", "invalid_change", "short_term", "s", "low", "[]", "2025-01-01T00:00:00Z", "v1"),
            )


# --- Connection behavior ---


def test_connection_commits_on_success(initialized_db):
    with get_connection(initialized_db) as conn:
        _insert_item(conn)

    # Read from a fresh connection to confirm persistence
    with get_connection(initialized_db) as conn:
        row = conn.execute("SELECT id FROM items WHERE id = ?", ("item-1",)).fetchone()
    assert row is not None
    assert row["id"] == "item-1"


def test_connection_rolls_back_on_error(initialized_db):
    with pytest.raises(RuntimeError):
        with get_connection(initialized_db) as conn:
            _insert_item(conn)
            raise RuntimeError("force rollback")

    with get_connection(initialized_db) as conn:
        row = conn.execute("SELECT id FROM items WHERE id = ?", ("item-1",)).fetchone()
    assert row is None


def test_row_factory_returns_row_objects(initialized_db):
    with get_connection(initialized_db) as conn:
        _insert_item(conn)
        row = conn.execute("SELECT id, title FROM items WHERE id = ?", ("item-1",)).fetchone()
    assert row["id"] == "item-1"
    assert row["title"] == "Title"
