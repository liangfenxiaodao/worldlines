"""Tests for worldlines.jobs — scheduled job functions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from worldlines.config import Config
from worldlines.ingestion.normalize import NormalizedItem, NormalizationResult
from worldlines.jobs import run_analysis, run_digest, run_ingestion, run_pipeline
from worldlines.storage.connection import get_connection
from worldlines.storage.schema import init_db


def _make_config(tmp_path, **overrides) -> Config:
    """Create a test Config pointing at a temp database and sources file."""
    db_path = str(tmp_path / "test.db")
    sources_path = str(tmp_path / "sources.json")

    # Write a default sources config
    sources = overrides.pop("_sources", {
        "adapters": [
            {
                "type": "rss",
                "enabled": True,
                "feeds": [
                    {"url": "https://example.com/feed", "source_name": "Test", "source_type": "news"}
                ],
            }
        ]
    })
    with open(sources_path, "w") as f:
        json.dump(sources, f)

    defaults = {
        "database_path": db_path,
        "llm_api_key": "test-key",
        "llm_model": "test-model",
        "telegram_bot_token": "test-token",
        "telegram_chat_id": "test-chat",
        "sources_config_path": sources_path,
        "max_items_per_source": 50,
        "analysis_version": "v1",
        "llm_temperature": 0.0,
        "llm_max_retries": 1,
        "llm_timeout_seconds": 10,
        "digest_timezone": "UTC",
        "digest_max_items": 20,
        "telegram_parse_mode": "HTML",
        "telegram_max_retries": 1,
    }
    defaults.update(overrides)
    return Config(**defaults)


def _seed_item(conn, item_id, title="Test Article"):
    """Insert a test item into the items table."""
    conn.execute(
        "INSERT INTO items "
        "(id, title, source_name, source_type, timestamp, content, "
        "canonical_link, ingested_at, dedup_hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            item_id, title, "Test Source", "news",
            "2025-06-15T08:00:00+00:00", "Article content here.",
            "https://example.com/1", "2025-06-15T08:01:00+00:00", f"hash-{item_id}",
        ),
    )


def _seed_analysis(conn, analysis_id, item_id):
    """Insert a test analysis into the analyses table."""
    conn.execute(
        "INSERT INTO analyses "
        "(id, item_id, dimensions, change_type, time_horizon, summary, "
        "importance, key_entities, analyzed_at, analysis_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            analysis_id, item_id,
            json.dumps([{"dimension": "compute_and_computational_paradigms", "relevance": "primary"}]),
            "reinforcing", "medium_term", f"Summary for {item_id}.",
            "medium", json.dumps(["TestEntity"]),
            "2025-06-15T10:00:00+00:00", "v1",
        ),
    )


# --- TestRunIngestion ---


class TestRunIngestion:
    @patch("worldlines.jobs.ingest_item")
    @patch("worldlines.jobs.RSSAdapter")
    def test_fetches_and_ingests_items(self, MockAdapter, mock_ingest, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        raw1 = MagicMock()
        raw2 = MagicMock()
        adapter_instance = MagicMock()
        adapter_instance.fetch.return_value = [raw1, raw2]
        MockAdapter.return_value = adapter_instance

        mock_ingest.return_value = NormalizationResult(
            status="new",
            item=MagicMock(spec=NormalizedItem),
        )

        run_ingestion(config)

        MockAdapter.assert_called_once_with(config.database_path, config.max_items_per_source)
        adapter_instance.configure.assert_called_once()
        adapter_instance.fetch.assert_called_once()
        assert mock_ingest.call_count == 2
        mock_ingest.assert_any_call(raw1, config.database_path)
        mock_ingest.assert_any_call(raw2, config.database_path)

    @patch("worldlines.jobs.ingest_item")
    @patch("worldlines.jobs.RSSAdapter")
    def test_counts_new_and_duplicates(self, MockAdapter, mock_ingest, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        adapter_instance = MagicMock()
        adapter_instance.fetch.return_value = [MagicMock(), MagicMock(), MagicMock()]
        MockAdapter.return_value = adapter_instance

        mock_ingest.side_effect = [
            NormalizationResult(status="new", item=MagicMock(spec=NormalizedItem)),
            NormalizationResult(
                status="duplicate", item=MagicMock(spec=NormalizedItem), duplicate_of="x"
            ),
            NormalizationResult(status="new", item=MagicMock(spec=NormalizedItem)),
        ]

        with patch("worldlines.jobs.logger") as mock_logger:
            run_ingestion(config)
            mock_logger.info.assert_any_call(
                "Ingestion complete: %d new, %d duplicates", 2, 1
            )

    @patch("worldlines.jobs.ingest_item")
    @patch("worldlines.jobs.RSSAdapter")
    def test_skips_disabled_adapters(self, MockAdapter, mock_ingest, tmp_path):
        sources = {
            "adapters": [
                {"type": "rss", "enabled": False, "feeds": [{"url": "http://x"}]}
            ]
        }
        config = _make_config(tmp_path, _sources=sources)
        init_db(config.database_path)

        run_ingestion(config)

        MockAdapter.assert_not_called()
        mock_ingest.assert_not_called()

    @patch("worldlines.jobs.ingest_item")
    @patch("worldlines.jobs.RSSAdapter")
    def test_skips_non_rss_adapters(self, MockAdapter, mock_ingest, tmp_path):
        sources = {
            "adapters": [
                {"type": "twitter", "enabled": True}
            ]
        }
        config = _make_config(tmp_path, _sources=sources)
        init_db(config.database_path)

        run_ingestion(config)

        MockAdapter.assert_not_called()


# --- TestRunAnalysis ---


class TestRunAnalysis:
    @patch("worldlines.jobs.classify_item")
    def test_finds_and_classifies_unanalyzed_items(self, mock_classify, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with get_connection(config.database_path) as conn:
            _seed_item(conn, "item-1", "Article One")
            _seed_item(conn, "item-2", "Article Two")
            # item-1 already analyzed
            _seed_analysis(conn, "a-1", "item-1")

        mock_classify.return_value = MagicMock(error=None)

        run_analysis(config)

        # Only item-2 should be classified
        assert mock_classify.call_count == 1
        call_item = mock_classify.call_args[0][0]
        assert call_item.id == "item-2"

    @patch("worldlines.jobs.classify_item")
    def test_passes_config_to_classify(self, mock_classify, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with get_connection(config.database_path) as conn:
            _seed_item(conn, "item-1")

        mock_classify.return_value = MagicMock(error=None)

        run_analysis(config)

        _, kwargs = mock_classify.call_args
        assert kwargs["api_key"] == "test-key"
        assert kwargs["model"] == "test-model"
        assert kwargs["analysis_version"] == "v1"
        assert kwargs["database_path"] == config.database_path
        assert kwargs["temperature"] == 0.0
        assert kwargs["max_retries"] == 1
        assert kwargs["timeout"] == 10

    @patch("worldlines.jobs.classify_item")
    def test_continues_on_error(self, mock_classify, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with get_connection(config.database_path) as conn:
            _seed_item(conn, "item-1", "Article One")
            _seed_item(conn, "item-2", "Article Two")

        mock_classify.side_effect = [
            Exception("API down"),
            MagicMock(error=None),
        ]

        run_analysis(config)

        # Both items should be attempted
        assert mock_classify.call_count == 2

    @patch("worldlines.jobs.classify_item")
    def test_logs_when_no_items(self, mock_classify, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with patch("worldlines.jobs.logger") as mock_logger:
            run_analysis(config)
            mock_logger.info.assert_any_call("Analysis: no unanalyzed items found")

        mock_classify.assert_not_called()

    @patch("worldlines.jobs.classify_item")
    def test_counts_errors_from_result(self, mock_classify, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with get_connection(config.database_path) as conn:
            _seed_item(conn, "item-1", "Article One")
            _seed_item(conn, "item-2", "Article Two")

        mock_classify.side_effect = [
            MagicMock(error={"code": "api_error", "message": "timeout"}),
            MagicMock(error=None),
        ]

        with patch("worldlines.jobs.logger") as mock_logger:
            run_analysis(config)
            mock_logger.info.assert_any_call(
                "Analysis complete: %d analyzed, %d errors", 1, 1
            )


# --- TestRunDigest ---


class TestRunDigest:
    @patch("worldlines.jobs.generate_digest")
    def test_calls_generate_digest_with_correct_args(self, mock_gen, tmp_path):
        config = _make_config(tmp_path)
        mock_gen.return_value = MagicMock(delivery_status="sent", error=None)

        with patch("worldlines.jobs.datetime") as mock_dt:
            fake_now = datetime(2025, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            run_digest(config)

        mock_gen.assert_called_once_with(
            "2025-06-15",
            "2025-06-15T00:00:00+00:00",
            database_path=config.database_path,
            bot_token="test-token",
            chat_id="test-chat",
            api_key="test-key",
            model="test-model",
            parse_mode="HTML",
            max_items=20,
            max_retries=1,
        )

    @patch("worldlines.jobs.generate_digest")
    def test_logs_delivery_status(self, mock_gen, tmp_path):
        config = _make_config(tmp_path)
        mock_gen.return_value = MagicMock(delivery_status="empty_day", error=None)

        with patch("worldlines.jobs.datetime") as mock_dt:
            fake_now = datetime(2025, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            with patch("worldlines.jobs.logger") as mock_logger:
                run_digest(config)
                mock_logger.info.assert_any_call(
                    "Digest delivery: status=%s, error=%s", "empty_day", None
                )


# --- TestRunPipeline ---


class TestRunPipeline:
    @patch("worldlines.jobs.run_analysis")
    @patch("worldlines.jobs.run_ingestion")
    def test_calls_ingestion_then_analysis(self, mock_ingest, mock_analyze, tmp_path):
        config = _make_config(tmp_path)

        call_order = []
        mock_ingest.side_effect = lambda c: call_order.append("ingestion")
        mock_analyze.side_effect = lambda c: call_order.append("analysis")

        run_pipeline(config)

        mock_ingest.assert_called_once_with(config)
        mock_analyze.assert_called_once_with(config)
        assert call_order == ["ingestion", "analysis"]
