"""Tests for worldlines.analysis.classifier — AI classification pipeline."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from worldlines.analysis.classifier import (
    AnalysisResult,
    classify_item,
    _parse_json,
    _persist_analysis,
)
from worldlines.ingestion.normalize import NormalizedItem
from worldlines.storage.connection import get_connection
from worldlines.storage.schema import init_db


VALID_LLM_RESPONSE = json.dumps({
    "dimensions": [
        {"dimension": "compute_and_computational_paradigms", "relevance": "primary"},
    ],
    "change_type": "reinforcing",
    "time_horizon": "medium_term",
    "summary": "TSMC expands advanced node capacity for AI accelerators.",
    "importance": "medium",
    "key_entities": ["TSMC"],
})


def _make_item(**overrides) -> NormalizedItem:
    """Create a test NormalizedItem."""
    defaults = {
        "id": "item-001",
        "title": "TSMC Expands Capacity",
        "source_name": "Semiconductor Engineering",
        "source_type": "industry",
        "timestamp": "2025-06-15T10:00:00+00:00",
        "content": "TSMC announces 2nm capacity expansion for AI chip production.",
        "canonical_link": "https://example.com/article",
        "ingested_at": "2025-06-15T10:01:00+00:00",
        "dedup_hash": "abc123",
    }
    defaults.update(overrides)
    return NormalizedItem(**defaults)


@pytest.fixture()
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    # Insert a test item so foreign key works
    with get_connection(path) as conn:
        conn.execute(
            "INSERT INTO items "
            "(id, title, source_name, source_type, timestamp, content, "
            "canonical_link, ingested_at, dedup_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("item-001", "TSMC Expands Capacity", "Semiconductor Engineering",
             "industry", "2025-06-15T10:00:00+00:00",
             "TSMC announces 2nm capacity expansion.",
             "https://example.com/article", "2025-06-15T10:01:00+00:00", "abc123"),
        )
    return path


def _mock_call_llm(**kwargs):
    """Mock _call_llm returning a valid JSON response."""
    return VALID_LLM_RESPONSE


# --- JSON parsing ---


class TestParseJson:
    def test_parses_clean_json(self):
        data = _parse_json('{"key": "value"}')
        assert data == {"key": "value"}

    def test_strips_markdown_fences(self):
        raw = '```json\n{"key": "value"}\n```'
        data = _parse_json(raw)
        assert data == {"key": "value"}

    def test_strips_plain_fences(self):
        raw = '```\n{"key": "value"}\n```'
        data = _parse_json(raw)
        assert data == {"key": "value"}

    def test_strips_whitespace(self):
        data = _parse_json('  \n{"key": "value"}\n  ')
        assert data == {"key": "value"}

    def test_raises_on_invalid_json(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            _parse_json("not json at all")

    def test_raises_on_partial_json(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            _parse_json('{"key": ')


# --- Persistence ---


class TestPersistAnalysis:
    def test_inserts_into_analyses_table(self, db_path):
        analysis = {
            "id": "analysis-001",
            "item_id": "item-001",
            "dimensions": [{"dimension": "compute_and_computational_paradigms", "relevance": "primary"}],
            "change_type": "reinforcing",
            "time_horizon": "medium_term",
            "summary": "Test summary.",
            "importance": "medium",
            "key_entities": ["TSMC"],
            "analyzed_at": "2025-06-15T10:02:00+00:00",
            "analysis_version": "v1",
        }
        _persist_analysis(analysis, db_path)

        with get_connection(db_path) as conn:
            row = conn.execute("SELECT * FROM analyses WHERE id = ?", ("analysis-001",)).fetchone()
        assert row is not None
        assert row["item_id"] == "item-001"
        assert row["change_type"] == "reinforcing"
        assert row["importance"] == "medium"
        assert row["analysis_version"] == "v1"
        assert json.loads(row["dimensions"]) == analysis["dimensions"]
        assert json.loads(row["key_entities"]) == ["TSMC"]


# --- classify_item ---


class TestClassifyItem:
    @patch("worldlines.analysis.classifier._call_llm", side_effect=_mock_call_llm)
    def test_returns_analysis_on_success(self, mock_llm, db_path):
        result = classify_item(
            _make_item(),
            api_key="test-key",
            model="test-model",
            analysis_version="v1",
            database_path=db_path,
        )
        assert isinstance(result, AnalysisResult)
        assert result.analysis is not None
        assert result.error is None

    @patch("worldlines.analysis.classifier._call_llm", side_effect=_mock_call_llm)
    def test_analysis_has_correct_fields(self, mock_llm, db_path):
        result = classify_item(
            _make_item(),
            api_key="test-key",
            model="test-model",
            analysis_version="v1",
            database_path=db_path,
        )
        a = result.analysis
        assert a["item_id"] == "item-001"
        assert a["change_type"] == "reinforcing"
        assert a["time_horizon"] == "medium_term"
        assert a["importance"] == "medium"
        assert a["analysis_version"] == "v1"
        assert len(a["id"]) > 0
        assert len(a["analyzed_at"]) > 0

    @patch("worldlines.analysis.classifier._call_llm", side_effect=_mock_call_llm)
    def test_persists_to_database(self, mock_llm, db_path):
        result = classify_item(
            _make_item(),
            api_key="test-key",
            model="test-model",
            analysis_version="v1",
            database_path=db_path,
        )
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM analyses WHERE id = ?",
                (result.analysis["id"],),
            ).fetchone()
        assert row is not None
        assert row["item_id"] == "item-001"

    @patch("worldlines.analysis.classifier._call_llm")
    def test_handles_api_error(self, mock_llm, db_path):
        mock_llm.side_effect = Exception("Connection timeout")
        result = classify_item(
            _make_item(),
            api_key="test-key",
            model="test-model",
            analysis_version="v1",
            database_path=db_path,
        )
        assert result.analysis is None
        assert result.error["code"] == "api_error"
        assert "Connection timeout" in result.error["message"]

    @patch("worldlines.analysis.classifier._call_llm")
    def test_handles_invalid_json(self, mock_llm, db_path):
        mock_llm.return_value = "This is not JSON"
        result = classify_item(
            _make_item(),
            api_key="test-key",
            model="test-model",
            analysis_version="v1",
            database_path=db_path,
        )
        assert result.analysis is None
        assert result.error["code"] == "parse_error"

    @patch("worldlines.analysis.classifier._call_llm")
    def test_handles_validation_failure(self, mock_llm, db_path):
        mock_llm.return_value = json.dumps({
            "dimensions": [],
            "change_type": "invalid",
            "time_horizon": "invalid",
            "summary": "",
            "importance": "invalid",
            "key_entities": [],
        })
        result = classify_item(
            _make_item(),
            api_key="test-key",
            model="test-model",
            analysis_version="v1",
            database_path=db_path,
        )
        assert result.analysis is None
        assert result.error["code"] == "classification_uncertain"

    @patch("worldlines.analysis.classifier._call_llm")
    def test_handles_forbidden_summary_terms(self, mock_llm, db_path):
        mock_llm.return_value = json.dumps({
            "dimensions": [
                {"dimension": "compute_and_computational_paradigms", "relevance": "primary"},
            ],
            "change_type": "reinforcing",
            "time_horizon": "medium_term",
            "summary": "This is a bullish development for chips.",
            "importance": "medium",
            "key_entities": ["TSMC"],
        })
        result = classify_item(
            _make_item(),
            api_key="test-key",
            model="test-model",
            analysis_version="v1",
            database_path=db_path,
        )
        assert result.analysis is None
        assert "bullish" in result.error["message"]

    @patch("worldlines.analysis.classifier._call_llm")
    def test_no_analysis_persisted_on_error(self, mock_llm, db_path):
        mock_llm.side_effect = Exception("API down")
        classify_item(
            _make_item(),
            api_key="test-key",
            model="test-model",
            analysis_version="v1",
            database_path=db_path,
        )
        with get_connection(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        assert count == 0

    @patch("worldlines.analysis.classifier._call_llm", side_effect=_mock_call_llm)
    def test_item_retained_on_error(self, mock_llm, db_path):
        # Item should still be in the database regardless of analysis outcome
        with get_connection(db_path) as conn:
            row = conn.execute("SELECT id FROM items WHERE id = ?", ("item-001",)).fetchone()
        assert row is not None

    @patch("worldlines.analysis.classifier._call_llm")
    def test_handles_markdown_wrapped_response(self, mock_llm, db_path):
        mock_llm.return_value = f"```json\n{VALID_LLM_RESPONSE}\n```"
        result = classify_item(
            _make_item(),
            api_key="test-key",
            model="test-model",
            analysis_version="v1",
            database_path=db_path,
        )
        assert result.analysis is not None
        assert result.error is None
