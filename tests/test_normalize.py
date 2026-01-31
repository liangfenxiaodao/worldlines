"""Tests for worldlines.ingestion.normalize — normalization pipeline."""

from __future__ import annotations

import uuid

import pytest

from worldlines.ingestion.dedup import compute_dedup_hash
from worldlines.ingestion.normalize import (
    NormalizedItem,
    RawSourceItem,
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
