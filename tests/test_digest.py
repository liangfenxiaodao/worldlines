"""Tests for worldlines.digest — Telegram digest pipeline."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from worldlines.digest.digest import (
    DigestData,
    DigestItem,
    DigestResult,
    _aggregate,
    _persist_digest,
    _query_analyses,
    generate_digest,
)
from worldlines.digest.renderer import (
    chunk_message,
    render_digest_html,
    render_empty_day_html,
)
from worldlines.digest.telegram import SendResult, send_message, send_messages
from worldlines.storage.connection import get_connection
from worldlines.storage.schema import init_db


# --- Fixtures ---


def _seed_item(conn, item_id, title="Test Article", canonical_link="https://example.com/1"):
    """Insert a test item into the items table."""
    conn.execute(
        "INSERT INTO items "
        "(id, title, source_name, source_type, timestamp, content, "
        "canonical_link, ingested_at, dedup_hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            item_id, title, "Test Source", "news",
            "2025-06-15T08:00:00+00:00", "Article content here.",
            canonical_link, "2025-06-15T08:01:00+00:00", f"hash-{item_id}",
        ),
    )


def _seed_analysis(
    conn, analysis_id, item_id, *,
    importance="medium", change_type="reinforcing", time_horizon="medium_term",
    dimensions=None, analyzed_at="2025-06-15T10:00:00+00:00",
):
    """Insert a test analysis into the analyses table."""
    if dimensions is None:
        dimensions = [{"dimension": "compute_and_computational_paradigms", "relevance": "primary"}]
    conn.execute(
        "INSERT INTO analyses "
        "(id, item_id, dimensions, change_type, time_horizon, summary, "
        "importance, key_entities, analyzed_at, analysis_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            analysis_id, item_id, json.dumps(dimensions),
            change_type, time_horizon, f"Summary for {item_id}.",
            importance, json.dumps(["TestEntity"]),
            analyzed_at, "v1",
        ),
    )


@pytest.fixture()
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture()
def seeded_db(db_path):
    """Database with varied items and analyses for digest testing."""
    with get_connection(db_path) as conn:
        # High importance — compute
        _seed_item(conn, "item-1", title="AI Chip Breakthrough")
        _seed_analysis(
            conn, "a-1", "item-1", importance="high", change_type="reinforcing",
            dimensions=[
                {"dimension": "compute_and_computational_paradigms", "relevance": "primary"},
            ],
        )
        # Medium importance — capital
        _seed_item(conn, "item-2", title="VC Funding Shifts")
        _seed_analysis(
            conn, "a-2", "item-2", importance="medium", change_type="early_signal",
            dimensions=[
                {"dimension": "capital_flows_and_business_models", "relevance": "primary"},
            ],
        )
        # Low importance — energy
        _seed_item(conn, "item-3", title="Minor Grid Update")
        _seed_analysis(
            conn, "a-3", "item-3", importance="low", change_type="neutral",
            dimensions=[
                {"dimension": "energy_resources_and_physical_constraints", "relevance": "primary"},
            ],
        )
        # Medium importance — governance + tech adoption (multi-dimension)
        _seed_item(conn, "item-4", title="EU <AI> Act Implementation")
        _seed_analysis(
            conn, "a-4", "item-4", importance="medium", change_type="friction",
            dimensions=[
                {"dimension": "governance_regulation_and_societal_response", "relevance": "primary"},
                {"dimension": "technology_adoption_and_industrial_diffusion", "relevance": "secondary"},
            ],
        )
    return db_path


# --- TestQueryAnalyses ---


class TestQueryAnalyses:
    def test_returns_rows_within_window(self, seeded_db):
        rows = _query_analyses(seeded_db, "2025-06-15T00:00:00", "2025-06-16T00:00:00")
        assert len(rows) == 4

    def test_excludes_rows_outside_window(self, seeded_db):
        rows = _query_analyses(seeded_db, "2025-06-16T00:00:00", "2025-06-17T00:00:00")
        assert len(rows) == 0

    def test_join_fields_present(self, seeded_db):
        rows = _query_analyses(seeded_db, "2025-06-15T00:00:00", "2025-06-16T00:00:00")
        row = rows[0]
        assert "analysis_id" in row
        assert "item_id" in row
        assert "title" in row
        assert "canonical_link" in row
        assert "dimensions" in row
        assert "change_type" in row
        assert "importance" in row

    def test_ordered_by_importance_then_date(self, seeded_db):
        rows = _query_analyses(seeded_db, "2025-06-15T00:00:00", "2025-06-16T00:00:00")
        importances = [r["importance"] for r in rows]
        assert importances[0] == "high"
        assert importances[-1] == "low"


# --- TestAggregate ---


class TestAggregate:
    def test_dimension_counting(self, seeded_db):
        rows = _query_analyses(seeded_db, "2025-06-15T00:00:00", "2025-06-16T00:00:00")
        data = _aggregate(rows, "2025-06-15", total_analyzed=4, max_items=20)
        assert data.dimension_breakdown["compute_and_computational_paradigms"] == 1
        assert data.dimension_breakdown["capital_flows_and_business_models"] == 1
        assert data.dimension_breakdown["energy_resources_and_physical_constraints"] == 1
        assert data.dimension_breakdown["governance_regulation_and_societal_response"] == 1
        assert data.dimension_breakdown["technology_adoption_and_industrial_diffusion"] == 1

    def test_change_type_distribution(self, seeded_db):
        rows = _query_analyses(seeded_db, "2025-06-15T00:00:00", "2025-06-16T00:00:00")
        data = _aggregate(rows, "2025-06-15", total_analyzed=4, max_items=20)
        assert data.change_type_distribution["reinforcing"] == 1
        assert data.change_type_distribution["early_signal"] == 1
        assert data.change_type_distribution["neutral"] == 1
        assert data.change_type_distribution["friction"] == 1

    def test_filters_to_medium_and_high(self, seeded_db):
        rows = _query_analyses(seeded_db, "2025-06-15T00:00:00", "2025-06-16T00:00:00")
        data = _aggregate(rows, "2025-06-15", total_analyzed=4, max_items=20)
        # item-3 is low importance, should be excluded from items
        assert data.item_count == 3
        item_ids = [it.item_id for it in data.items]
        assert "item-3" not in item_ids

    def test_max_items_cap(self, seeded_db):
        rows = _query_analyses(seeded_db, "2025-06-15T00:00:00", "2025-06-16T00:00:00")
        data = _aggregate(rows, "2025-06-15", total_analyzed=4, max_items=1)
        assert data.item_count == 1

    def test_total_analyzed_reflects_all_rows(self, seeded_db):
        rows = _query_analyses(seeded_db, "2025-06-15T00:00:00", "2025-06-16T00:00:00")
        data = _aggregate(rows, "2025-06-15", total_analyzed=4, max_items=20)
        assert data.total_analyzed == 4

    def test_empty_rows(self):
        data = _aggregate([], "2025-06-15", total_analyzed=0, max_items=20)
        assert data.item_count == 0
        assert data.items == []
        assert data.dimension_breakdown == {}
        assert data.change_type_distribution == {}


# --- TestRenderDigestHtml ---


class TestRenderDigestHtml:
    def _make_data(self):
        items = [
            DigestItem(
                item_id="item-1", analysis_id="a-1",
                title="AI Chip Breakthrough",
                summary="New chip architecture improves efficiency.",
                dimensions=["compute_and_computational_paradigms"],
                change_type="reinforcing", time_horizon="medium_term",
                importance="high", canonical_link="https://example.com/1",
            ),
            DigestItem(
                item_id="item-2", analysis_id="a-2",
                title="EU <AI> Act",
                summary="Regulation impacts adoption.",
                dimensions=["governance_regulation_and_societal_response"],
                change_type="friction", time_horizon="long_term",
                importance="medium", canonical_link=None,
            ),
        ]
        return DigestData(
            digest_date="2025-06-15",
            total_analyzed=5,
            item_count=2,
            dimension_breakdown={
                "compute_and_computational_paradigms": 3,
                "governance_regulation_and_societal_response": 2,
            },
            change_type_distribution={"reinforcing": 3, "friction": 2},
            items=items,
        )

    def test_contains_header(self):
        html = render_digest_html(self._make_data())
        assert "<b>Worldlines Daily Digest</b>" in html
        assert "2025-06-15" in html
        assert "5 items analyzed" in html

    def test_contains_dimension_breakdown(self):
        html = render_digest_html(self._make_data())
        assert "Compute & Computational Paradigms: 3" in html
        assert "Governance, Regulation & Societal Response: 2" in html

    def test_contains_change_types(self):
        html = render_digest_html(self._make_data())
        assert "Reinforcing: 3" in html
        assert "Friction: 2" in html

    def test_contains_items(self):
        html = render_digest_html(self._make_data())
        assert "AI Chip Breakthrough" in html
        assert "reinforcing | medium_term | high" in html
        assert "New chip architecture improves efficiency." in html

    def test_html_escaping(self):
        html = render_digest_html(self._make_data())
        # Title with angle brackets should be escaped
        assert "EU &lt;AI&gt; Act" in html

    def test_source_link_present(self):
        html = render_digest_html(self._make_data())
        assert '<a href="https://example.com/1">Source</a>' in html

    def test_no_source_link_when_none(self):
        html = render_digest_html(self._make_data())
        # Second item has no link — should not have a Source line for it
        # Count Source links — should be exactly 1
        assert html.count(">Source</a>") == 1


# --- TestRenderEmptyDayHtml ---


class TestRenderEmptyDayHtml:
    def test_contains_date(self):
        html = render_empty_day_html("2025-06-15")
        assert "2025-06-15" in html

    def test_contains_no_items_message(self):
        html = render_empty_day_html("2025-06-15")
        assert "No items to report today." in html

    def test_is_short(self):
        html = render_empty_day_html("2025-06-15")
        assert len(html) < 200


# --- TestChunkMessage ---


class TestChunkMessage:
    def test_single_chunk_when_short(self):
        text = "Short message"
        chunks = chunk_message(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_splits_on_paragraph_boundary(self):
        para1 = "A" * 100
        para2 = "B" * 100
        text = f"{para1}\n\n{para2}"
        chunks = chunk_message(text, max_length=150)
        assert len(chunks) == 2
        assert chunks[0] == para1
        assert chunks[1] == para2

    def test_falls_back_to_line_boundary(self):
        line1 = "A" * 100
        line2 = "B" * 100
        text = f"{line1}\n{line2}"
        chunks = chunk_message(text, max_length=150)
        assert len(chunks) == 2
        assert chunks[0] == line1
        assert chunks[1] == line2

    def test_hard_split_when_no_boundary(self):
        text = "A" * 200
        chunks = chunk_message(text, max_length=100)
        assert len(chunks) == 2
        assert chunks[0] == "A" * 100
        assert chunks[1] == "A" * 100

    def test_no_content_lost(self):
        para1 = "A" * 100
        para2 = "B" * 50
        para3 = "C" * 80
        text = f"{para1}\n\n{para2}\n\n{para3}"
        chunks = chunk_message(text, max_length=120)
        reassembled = "".join(c.replace("\n", "") for c in chunks)
        original_content = text.replace("\n", "")
        assert reassembled == original_content


# --- TestSendMessage ---


class TestSendMessage:
    @patch("worldlines.digest.telegram.httpx.post")
    def test_success(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {"ok": True, "result": {"message_id": 42}},
        )
        result = send_message("token", "chat", "hello")
        assert result.ok is True
        assert result.message_id == 42
        assert result.error is None

    @patch("worldlines.digest.telegram.time.sleep")
    @patch("worldlines.digest.telegram.httpx.post")
    def test_retries_on_failure(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            MagicMock(json=lambda: {"ok": False, "description": "Too Many Requests"}),
            MagicMock(json=lambda: {"ok": True, "result": {"message_id": 43}}),
        ]
        result = send_message("token", "chat", "hello", max_retries=3)
        assert result.ok is True
        assert result.message_id == 43
        mock_sleep.assert_called_once_with(1)  # 2^0 = 1

    @patch("worldlines.digest.telegram.time.sleep")
    @patch("worldlines.digest.telegram.httpx.post")
    def test_max_retries_exhausted(self, mock_post, mock_sleep):
        mock_post.return_value = MagicMock(
            json=lambda: {"ok": False, "description": "Bad Request"},
        )
        result = send_message("token", "chat", "hello", max_retries=3)
        assert result.ok is False
        assert result.error == "Bad Request"
        assert mock_post.call_count == 3

    @patch("worldlines.digest.telegram.time.sleep")
    @patch("worldlines.digest.telegram.httpx.post")
    def test_backoff_timing(self, mock_post, mock_sleep):
        mock_post.side_effect = Exception("Network error")
        send_message("token", "chat", "hello", max_retries=3)
        calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert calls == [1, 2]  # 2^0, 2^1 (no sleep after last attempt)

    @patch("worldlines.digest.telegram.httpx.post")
    def test_exception_returns_send_result(self, mock_post):
        mock_post.side_effect = Exception("Connection refused")
        result = send_message("token", "chat", "hello", max_retries=1)
        assert result.ok is False
        assert "Connection refused" in result.error


# --- TestSendMessages ---


class TestSendMessages:
    @patch("worldlines.digest.telegram.httpx.post")
    def test_all_chunks_sent(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {"ok": True, "result": {"message_id": 1}},
        )
        results = send_messages("token", "chat", ["chunk1", "chunk2", "chunk3"])
        assert len(results) == 3
        assert all(r.ok for r in results)

    @patch("worldlines.digest.telegram.time.sleep")
    @patch("worldlines.digest.telegram.httpx.post")
    def test_stops_on_first_failure(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            MagicMock(json=lambda: {"ok": True, "result": {"message_id": 1}}),
            MagicMock(json=lambda: {"ok": False, "description": "error"}),
            MagicMock(json=lambda: {"ok": False, "description": "error"}),
            MagicMock(json=lambda: {"ok": False, "description": "error"}),
        ]
        results = send_messages("token", "chat", ["c1", "c2", "c3"], max_retries=1)
        assert len(results) == 2
        assert results[0].ok is True
        assert results[1].ok is False


# --- TestPersistDigest ---


class TestPersistDigest:
    def test_inserts_record(self, db_path):
        record = {
            "id": "digest-001",
            "digest_date": "2025-06-15",
            "item_count": 3,
            "dimension_breakdown": {"compute_and_computational_paradigms": 2},
            "change_type_distribution": {"reinforcing": 2, "friction": 1},
            "high_importance_items": [{"item_id": "item-1", "analysis_id": "a-1"}],
            "message_text": "<b>Test</b>",
            "sent_at": "2025-06-15T18:00:00+00:00",
            "telegram_message_ids": [42],
        }
        _persist_digest(record, db_path)
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM digests WHERE id = ?", ("digest-001",),
            ).fetchone()
        assert row is not None
        assert row["digest_date"] == "2025-06-15"
        assert row["item_count"] == 3
        assert json.loads(row["dimension_breakdown"]) == record["dimension_breakdown"]
        assert json.loads(row["telegram_message_ids"]) == [42]

    def test_unique_constraint_on_date(self, db_path):
        record = {
            "id": "digest-001",
            "digest_date": "2025-06-15",
            "item_count": 0,
            "dimension_breakdown": {},
            "change_type_distribution": {},
            "high_importance_items": [],
            "message_text": "test",
            "sent_at": "2025-06-15T18:00:00+00:00",
            "telegram_message_ids": [],
        }
        _persist_digest(record, db_path)
        record2 = dict(record, id="digest-002")
        with pytest.raises(Exception):
            _persist_digest(record2, db_path)


# --- TestGenerateDigest (integration with mocked Telegram) ---


class TestGenerateDigest:
    @patch("worldlines.digest.digest.send_messages")
    def test_sent_status(self, mock_send, seeded_db):
        mock_send.return_value = [SendResult(ok=True, message_id=100)]
        result = generate_digest(
            "2025-06-15", "2025-06-15T00:00:00",
            database_path=seeded_db, bot_token="tok", chat_id="cid",
        )
        assert isinstance(result, DigestResult)
        assert result.delivery_status == "sent"
        assert result.error is None
        assert result.digest_record is not None
        assert result.digest_record["item_count"] == 3  # high + medium (not low)

    @patch("worldlines.digest.digest.send_messages")
    def test_empty_day_status(self, mock_send, db_path):
        mock_send.return_value = [SendResult(ok=True, message_id=101)]
        result = generate_digest(
            "2025-06-15", "2025-06-15T00:00:00",
            database_path=db_path, bot_token="tok", chat_id="cid",
        )
        assert result.delivery_status == "empty_day"
        assert result.digest_record is not None
        assert result.digest_record["item_count"] == 0

    @patch("worldlines.digest.digest.send_messages")
    def test_failed_status_on_send_error(self, mock_send, seeded_db):
        mock_send.return_value = [SendResult(ok=False, error="Telegram down")]
        result = generate_digest(
            "2025-06-15", "2025-06-15T00:00:00",
            database_path=seeded_db, bot_token="tok", chat_id="cid",
        )
        assert result.delivery_status == "failed"
        assert result.error == "Telegram down"
        # Record still persisted
        assert result.digest_record is not None

    @patch("worldlines.digest.digest.send_messages")
    def test_duplicate_date_returns_failed(self, mock_send, seeded_db):
        mock_send.return_value = [SendResult(ok=True, message_id=102)]
        # First digest
        generate_digest(
            "2025-06-15", "2025-06-15T00:00:00",
            database_path=seeded_db, bot_token="tok", chat_id="cid",
        )
        # Second digest for same date
        result = generate_digest(
            "2025-06-15", "2025-06-15T00:00:00",
            database_path=seeded_db, bot_token="tok", chat_id="cid",
        )
        assert result.delivery_status == "failed"
        assert "Duplicate" in result.error

    @patch("worldlines.digest.digest.send_messages")
    def test_persists_to_database(self, mock_send, seeded_db):
        mock_send.return_value = [SendResult(ok=True, message_id=103)]
        result = generate_digest(
            "2025-06-15", "2025-06-15T00:00:00",
            database_path=seeded_db, bot_token="tok", chat_id="cid",
        )
        with get_connection(seeded_db) as conn:
            row = conn.execute(
                "SELECT * FROM digests WHERE id = ?",
                (result.digest_record["id"],),
            ).fetchone()
        assert row is not None
        assert row["digest_date"] == "2025-06-15"
        assert row["item_count"] == 3

    @patch("worldlines.digest.digest.send_messages")
    def test_message_ids_captured(self, mock_send, seeded_db):
        mock_send.return_value = [
            SendResult(ok=True, message_id=200),
            SendResult(ok=True, message_id=201),
        ]
        result = generate_digest(
            "2025-06-15", "2025-06-15T00:00:00",
            database_path=seeded_db, bot_token="tok", chat_id="cid",
        )
        assert result.digest_record["telegram_message_ids"] == [200, 201]
