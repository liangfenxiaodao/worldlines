"""Tests for worldlines.ingestion.normalize — normalization pipeline."""

from __future__ import annotations

import json
import uuid

import pytest

from worldlines.ingestion.dedup import compute_dedup_hash
from worldlines.ingestion.normalize import (
    NormalizedItem,
    RawSourceItem,
    ingest_item,
    normalize,
    persist_item,
    _validate_raw_item,
)
from worldlines.storage.connection import get_connection
from worldlines.storage.schema import init_db


def _make_raw(**overrides) -> RawSourceItem:
    """Create a valid RawSourceItem with optional field overrides."""
    defaults = {
        "source_name": "Test Source",
        "source_type": "news",
        "title": "Test Title",
        "content": "Test content body.",
        "url": "https://example.com/article",
        "published_at": "2025-06-15T10:00:00+00:00",
    }
    defaults.update(overrides)
    return RawSourceItem(**defaults)


@pytest.fixture()
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


# --- Validation ---


class TestValidation:
    def test_valid_item_no_errors(self):
        assert _validate_raw_item(_make_raw()) == []

    def test_empty_title(self):
        errors = _validate_raw_item(_make_raw(title=""))
        assert any("title" in e for e in errors)

    def test_whitespace_only_title(self):
        errors = _validate_raw_item(_make_raw(title="   "))
        assert any("title" in e for e in errors)

    def test_empty_source_name(self):
        errors = _validate_raw_item(_make_raw(source_name=""))
        assert any("source_name" in e for e in errors)

    def test_empty_source_type(self):
        errors = _validate_raw_item(_make_raw(source_type=""))
        assert any("source_type" in e for e in errors)

    def test_invalid_source_type(self):
        errors = _validate_raw_item(_make_raw(source_type="blog"))
        assert any("source_type" in e and "blog" in e for e in errors)

    def test_all_valid_source_types(self):
        for st in ["news", "filing", "transcript", "report", "research",
                    "government", "policy", "industry", "other"]:
            assert _validate_raw_item(_make_raw(source_type=st)) == []

    def test_empty_content(self):
        errors = _validate_raw_item(_make_raw(content=""))
        assert any("content" in e for e in errors)

    def test_invalid_published_at(self):
        errors = _validate_raw_item(_make_raw(published_at="not-a-date"))
        assert any("published_at" in e for e in errors)

    def test_null_published_at_is_valid(self):
        assert _validate_raw_item(_make_raw(published_at=None)) == []

    def test_null_url_is_valid(self):
        assert _validate_raw_item(_make_raw(url=None)) == []

    def test_multiple_errors_reported(self):
        errors = _validate_raw_item(_make_raw(title="", content="", source_name=""))
        assert len(errors) >= 3


# --- Normalize ---


class TestNormalize:
    def test_produces_normalized_item(self):
        item = normalize(_make_raw())
        assert isinstance(item, NormalizedItem)

    def test_generates_uuid(self):
        item = normalize(_make_raw())
        parsed = uuid.UUID(item.id)
        assert parsed.version == 4

    def test_unique_ids(self):
        a = normalize(_make_raw())
        b = normalize(_make_raw())
        assert a.id != b.id

    def test_copies_title(self):
        item = normalize(_make_raw(title="My Title"))
        assert item.title == "My Title"

    def test_copies_source_fields(self):
        item = normalize(_make_raw(source_name="FT", source_type="news"))
        assert item.source_name == "FT"
        assert item.source_type == "news"

    def test_copies_content(self):
        item = normalize(_make_raw(content="Body text"))
        assert item.content == "Body text"

    def test_maps_url_to_canonical_link(self):
        item = normalize(_make_raw(url="https://example.com"))
        assert item.canonical_link == "https://example.com"

    def test_null_url_maps_to_null_canonical_link(self):
        item = normalize(_make_raw(url=None))
        assert item.canonical_link is None

    def test_uses_published_at_as_timestamp(self):
        item = normalize(_make_raw(published_at="2025-06-15T10:00:00+00:00"))
        assert item.timestamp == "2025-06-15T10:00:00+00:00"

    def test_falls_back_to_ingestion_time_when_no_published_at(self):
        item = normalize(_make_raw(published_at=None))
        assert item.timestamp == item.ingested_at

    def test_ingested_at_is_iso8601(self):
        item = normalize(_make_raw())
        # Should parse without error
        from datetime import datetime
        datetime.fromisoformat(item.ingested_at)

    def test_computes_dedup_hash(self):
        raw = _make_raw()
        item = normalize(raw)
        expected = compute_dedup_hash(raw.title, raw.source_name, raw.content)
        assert item.dedup_hash == expected

    def test_same_input_same_dedup_hash(self):
        a = normalize(_make_raw())
        b = normalize(_make_raw())
        assert a.dedup_hash == b.dedup_hash

    def test_raises_on_invalid_input(self):
        with pytest.raises(ValueError, match="Invalid RawSourceItem"):
            normalize(_make_raw(title=""))

    def test_error_message_includes_all_failures(self):
        with pytest.raises(ValueError, match="title.*content"):
            normalize(_make_raw(title="", content=""))


# --- Persist ---


class TestPersistItem:
    def test_persists_to_database(self, db_path):
        item = normalize(_make_raw())
        persist_item(item, db_path)

        with get_connection(db_path) as conn:
            row = conn.execute("SELECT * FROM items WHERE id = ?", (item.id,)).fetchone()
        assert row is not None
        assert row["title"] == item.title
        assert row["source_name"] == item.source_name
        assert row["source_type"] == item.source_type
        assert row["timestamp"] == item.timestamp
        assert row["content"] == item.content
        assert row["canonical_link"] == item.canonical_link
        assert row["ingested_at"] == item.ingested_at
        assert row["dedup_hash"] == item.dedup_hash

    def test_persists_null_canonical_link(self, db_path):
        item = normalize(_make_raw(url=None))
        persist_item(item, db_path)

        with get_connection(db_path) as conn:
            row = conn.execute("SELECT canonical_link FROM items WHERE id = ?", (item.id,)).fetchone()
        assert row["canonical_link"] is None

    def test_duplicate_dedup_hash_raises(self, db_path):
        item_a = normalize(_make_raw())
        persist_item(item_a, db_path)

        # Same raw input produces same dedup_hash but different id
        item_b = normalize(_make_raw())
        with pytest.raises(Exception):  # sqlite3.IntegrityError
            persist_item(item_b, db_path)

    def test_different_items_both_persist(self, db_path):
        item_a = normalize(_make_raw(title="Article A"))
        item_b = normalize(_make_raw(title="Article B"))
        persist_item(item_a, db_path)
        persist_item(item_b, db_path)

        with get_connection(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        assert count == 2


# --- Ingest (normalize + deduplicate) ---


class TestIngestItem:
    def test_new_item_returns_status_new(self, db_path):
        result = ingest_item(_make_raw(), db_path)
        assert result.status == "new"
        assert result.duplicate_of is None

    def test_new_item_is_persisted(self, db_path):
        result = ingest_item(_make_raw(), db_path)

        with get_connection(db_path) as conn:
            row = conn.execute("SELECT id FROM items WHERE id = ?", (result.item.id,)).fetchone()
        assert row is not None

    def test_new_item_returns_normalized_item(self, db_path):
        result = ingest_item(_make_raw(title="My Article"), db_path)
        assert isinstance(result.item, NormalizedItem)
        assert result.item.title == "My Article"

    def test_duplicate_returns_status_duplicate(self, db_path):
        ingest_item(_make_raw(), db_path)
        result = ingest_item(_make_raw(), db_path)
        assert result.status == "duplicate"

    def test_duplicate_returns_canonical_id(self, db_path):
        first = ingest_item(_make_raw(), db_path)
        second = ingest_item(_make_raw(), db_path)
        assert second.duplicate_of == first.item.id

    def test_duplicate_is_not_persisted_to_items(self, db_path):
        ingest_item(_make_raw(), db_path)
        second = ingest_item(_make_raw(), db_path)

        with get_connection(db_path) as conn:
            row = conn.execute("SELECT id FROM items WHERE id = ?", (second.item.id,)).fetchone()
        assert row is None

    def test_duplicate_creates_dedup_record(self, db_path):
        first = ingest_item(_make_raw(), db_path)
        second = ingest_item(_make_raw(), db_path)

        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM deduplication_records WHERE canonical_item_id = ?",
                (first.item.id,),
            ).fetchone()
        assert row is not None
        assert json.loads(row["duplicate_item_ids"]) == [second.item.id]
        assert row["method"] == "hash_exact"

    def test_dedup_record_has_timestamp(self, db_path):
        from datetime import datetime

        first = ingest_item(_make_raw(), db_path)
        ingest_item(_make_raw(), db_path)

        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT deduped_at FROM deduplication_records WHERE canonical_item_id = ?",
                (first.item.id,),
            ).fetchone()
        # Should parse without error
        datetime.fromisoformat(row["deduped_at"])

    def test_multiple_duplicates_create_separate_records(self, db_path):
        first = ingest_item(_make_raw(), db_path)
        ingest_item(_make_raw(), db_path)
        ingest_item(_make_raw(), db_path)

        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM deduplication_records WHERE canonical_item_id = ?",
                (first.item.id,),
            ).fetchall()
        assert len(rows) == 2

    def test_different_items_both_ingested(self, db_path):
        a = ingest_item(_make_raw(title="Article A"), db_path)
        b = ingest_item(_make_raw(title="Article B"), db_path)
        assert a.status == "new"
        assert b.status == "new"

        with get_connection(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        assert count == 2

    def test_invalid_item_raises(self, db_path):
        with pytest.raises(ValueError, match="Invalid RawSourceItem"):
            ingest_item(_make_raw(title=""), db_path)
