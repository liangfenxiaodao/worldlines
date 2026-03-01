"""Tests for worldlines.jobs — scheduled job functions."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from worldlines.config import Config
from worldlines.ingestion.normalize import NormalizedItem, NormalizationResult
from worldlines.jobs import (
    _check_ingestion_stall,
    _record_source_failure,
    _record_source_success,
    _send_alert,
    run_analysis,
    run_digest,
    run_exposure_mapping,
    run_ingestion,
    run_pipeline,
)
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
    @patch("worldlines.jobs.get_adapter_class")
    def test_fetches_and_ingests_items(self, mock_get_cls, mock_ingest, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        raw1 = MagicMock()
        raw2 = MagicMock()
        adapter_instance = MagicMock()
        adapter_instance.name = "rss"
        adapter_instance.fetch.return_value = [raw1, raw2]
        MockAdapter = MagicMock(return_value=adapter_instance)
        mock_get_cls.return_value = MockAdapter

        mock_ingest.return_value = NormalizationResult(
            status="new",
            item=MagicMock(spec=NormalizedItem),
        )

        run_ingestion(config)

        MockAdapter.assert_called_once_with(config.database_path, config.max_items_per_source)
        adapter_instance.configure.assert_called_once()
        adapter_instance.fetch.assert_called_once()
        assert mock_ingest.call_count == 2
        mock_ingest.assert_any_call(
            raw1, config.database_path,
            similarity_threshold=config.similarity_dedup_threshold,
            similarity_window_hours=config.similarity_dedup_window_hours,
        )
        mock_ingest.assert_any_call(
            raw2, config.database_path,
            similarity_threshold=config.similarity_dedup_threshold,
            similarity_window_hours=config.similarity_dedup_window_hours,
        )

    @patch("worldlines.jobs.ingest_item")
    @patch("worldlines.jobs.get_adapter_class")
    def test_counts_new_and_duplicates(self, mock_get_cls, mock_ingest, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        adapter_instance = MagicMock()
        adapter_instance.name = "rss"
        adapter_instance.fetch.return_value = [MagicMock(), MagicMock(), MagicMock()]
        MockAdapter = MagicMock(return_value=adapter_instance)
        mock_get_cls.return_value = MockAdapter

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
    @patch("worldlines.jobs.get_adapter_class")
    def test_skips_disabled_adapters(self, mock_get_cls, mock_ingest, tmp_path):
        sources = {
            "adapters": [
                {"type": "rss", "enabled": False, "feeds": [{"url": "http://x"}]}
            ]
        }
        config = _make_config(tmp_path, _sources=sources)
        init_db(config.database_path)

        MockAdapter = MagicMock()
        mock_get_cls.return_value = MockAdapter

        run_ingestion(config)

        MockAdapter.assert_not_called()
        mock_ingest.assert_not_called()

    @patch("worldlines.jobs.ingest_item")
    def test_skips_unknown_adapter_types(self, mock_ingest, tmp_path):
        sources = {
            "adapters": [
                {"type": "twitter", "enabled": True}
            ]
        }
        config = _make_config(tmp_path, _sources=sources)
        init_db(config.database_path)

        with patch("worldlines.jobs.logger") as mock_logger:
            run_ingestion(config)
            mock_logger.warning.assert_any_call(
                "Unknown adapter type '%s', skipping", "twitter"
            )

        mock_ingest.assert_not_called()


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
            MagicMock(error={"code": "parse_error", "message": "bad json"}),
            MagicMock(error=None),
        ]

        with patch("worldlines.jobs.logger") as mock_logger:
            run_analysis(config)
            mock_logger.info.assert_any_call(
                "Analysis complete: %d analyzed, %d errors", 1, 1
            )

    @patch("worldlines.jobs.classify_item")
    def test_api_error_does_not_record_analysis_error(self, mock_classify, tmp_path):
        """Transient API errors (billing, rate limits) should not count toward retry limit."""
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with get_connection(config.database_path) as conn:
            _seed_item(conn, "item-1", "Article One")

        mock_classify.return_value = MagicMock(
            error={"code": "api_error", "message": "credit balance too low"}
        )

        run_analysis(config)

        with get_connection(config.database_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM analysis_errors").fetchone()[0]
        assert count == 0

    @patch("worldlines.jobs.classify_item")
    def test_parse_error_records_analysis_error(self, mock_classify, tmp_path):
        """Item-specific errors (parse, validation) should count toward retry limit."""
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with get_connection(config.database_path) as conn:
            _seed_item(conn, "item-1", "Article One")

        mock_classify.return_value = MagicMock(
            error={"code": "parse_error", "message": "invalid JSON"}
        )

        run_analysis(config)

        with get_connection(config.database_path) as conn:
            row = conn.execute(
                "SELECT attempt_count FROM analysis_errors WHERE item_id = ?",
                ("item-1",),
            ).fetchone()
        assert row is not None
        assert row["attempt_count"] == 1

    @patch("worldlines.jobs.classify_item")
    def test_api_error_stops_analysis_early(self, mock_classify, tmp_path):
        """An api_error on one item should stop processing remaining items."""
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with get_connection(config.database_path) as conn:
            _seed_item(conn, "item-1", "Article One")
            _seed_item(conn, "item-2", "Article Two")

        mock_classify.return_value = MagicMock(
            error={"code": "api_error", "message": "credit balance too low"}
        )

        run_analysis(config)

        # Should stop after first api_error, not attempt item-2
        assert mock_classify.call_count == 1


def _seed_eligible_analysis(conn, analysis_id, item_id):
    """Insert a test analysis eligible for exposure mapping."""
    conn.execute(
        "INSERT INTO analyses "
        "(id, item_id, dimensions, change_type, time_horizon, summary, "
        "importance, key_entities, analyzed_at, analysis_version, "
        "eligible_for_exposure_mapping) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            analysis_id, item_id,
            json.dumps([{"dimension": "compute_and_computational_paradigms", "relevance": "primary"}]),
            "reinforcing", "medium_term", f"Summary for {item_id}.",
            "high", json.dumps(["TestEntity"]),
            "2025-06-15T10:00:00+00:00", "v1", 1,
        ),
    )


# --- TestRunExposureMapping ---


class TestRunExposureMapping:
    @patch("worldlines.jobs.map_exposures")
    def test_finds_and_maps_eligible_analyses(self, mock_map, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with get_connection(config.database_path) as conn:
            _seed_item(conn, "item-1", "Article One")
            _seed_item(conn, "item-2", "Article Two")
            # item-1 eligible, item-2 not eligible (low importance)
            _seed_eligible_analysis(conn, "a-1", "item-1")
            _seed_analysis(conn, "a-2", "item-2")  # default is medium, but eligible_for_exposure_mapping=0 by default

        mock_map.return_value = MagicMock(error=None, skipped_reason=None)

        run_exposure_mapping(config)

        # Only a-1 should be mapped (eligible=1 and no existing exposure)
        assert mock_map.call_count == 1
        call_analysis = mock_map.call_args[0][0]
        assert call_analysis["analysis_id"] == "a-1"

    @patch("worldlines.jobs.map_exposures")
    def test_skips_already_mapped(self, mock_map, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with get_connection(config.database_path) as conn:
            _seed_item(conn, "item-1", "Article One")
            _seed_eligible_analysis(conn, "a-1", "item-1")
            # Already has an exposure record
            conn.execute(
                "INSERT INTO exposures (id, analysis_id, exposures, mapped_at) "
                "VALUES (?, ?, ?, ?)",
                ("e-1", "a-1", "[]", "2025-06-15T11:00:00+00:00"),
            )

        run_exposure_mapping(config)

        mock_map.assert_not_called()

    @patch("worldlines.jobs.map_exposures")
    def test_error_handling(self, mock_map, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with get_connection(config.database_path) as conn:
            _seed_item(conn, "item-1", "Article One")
            _seed_eligible_analysis(conn, "a-1", "item-1")

        mock_map.return_value = MagicMock(
            error={"code": "parse_error", "message": "bad json"},
            skipped_reason=None,
        )

        run_exposure_mapping(config)

        with get_connection(config.database_path) as conn:
            row = conn.execute(
                "SELECT attempt_count FROM exposure_errors WHERE analysis_id = ?",
                ("a-1",),
            ).fetchone()
        assert row is not None
        assert row["attempt_count"] == 1

    @patch("worldlines.jobs.map_exposures")
    def test_api_error_does_not_record_exposure_error(self, mock_map, tmp_path):
        """Transient API errors should not count toward retry limit."""
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with get_connection(config.database_path) as conn:
            _seed_item(conn, "item-1", "Article One")
            _seed_eligible_analysis(conn, "a-1", "item-1")

        mock_map.return_value = MagicMock(
            error={"code": "api_error", "message": "timeout"},
            skipped_reason=None,
        )

        run_exposure_mapping(config)

        with get_connection(config.database_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM exposure_errors").fetchone()[0]
        assert count == 0

    @patch("worldlines.jobs.map_exposures")
    def test_continues_on_unexpected_error(self, mock_map, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with get_connection(config.database_path) as conn:
            _seed_item(conn, "item-1", "Article One")
            _seed_item(conn, "item-2", "Article Two")
            _seed_eligible_analysis(conn, "a-1", "item-1")
            _seed_eligible_analysis(conn, "a-2", "item-2")

        mock_map.side_effect = [
            Exception("unexpected"),
            MagicMock(error=None, skipped_reason=None),
        ]

        run_exposure_mapping(config)

        assert mock_map.call_count == 2

    @patch("worldlines.jobs.map_exposures")
    def test_logs_when_no_eligible(self, mock_map, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with patch("worldlines.jobs.logger") as mock_logger:
            run_exposure_mapping(config)
            mock_logger.info.assert_any_call(
                "Exposure mapping: no eligible unmapped analyses found"
            )

        mock_map.assert_not_called()

    @patch("worldlines.jobs.map_exposures")
    def test_api_error_stops_mapping_early(self, mock_map, tmp_path):
        """An api_error on one analysis should stop processing remaining analyses."""
        config = _make_config(tmp_path)
        init_db(config.database_path)

        with get_connection(config.database_path) as conn:
            _seed_item(conn, "item-1", "Article One")
            _seed_item(conn, "item-2", "Article Two")
            _seed_eligible_analysis(conn, "a-1", "item-1")
            _seed_eligible_analysis(conn, "a-2", "item-2")

        mock_map.return_value = MagicMock(
            error={"code": "api_error", "message": "credit balance too low"},
            skipped_reason=None,
        )

        run_exposure_mapping(config)

        # Should stop after first api_error, not attempt a-2
        assert mock_map.call_count == 1

    @patch("worldlines.jobs.map_exposures")
    def test_respects_max_per_run_limit(self, mock_map, tmp_path):
        """exposure_max_per_run should cap the number of analyses processed per cycle."""
        config = _make_config(tmp_path, exposure_max_per_run=2)
        init_db(config.database_path)

        with get_connection(config.database_path) as conn:
            for i in range(1, 5):
                _seed_item(conn, f"item-{i}", f"Article {i}")
                _seed_eligible_analysis(conn, f"a-{i}", f"item-{i}")

        mock_map.return_value = MagicMock(error=None, skipped_reason=None)

        run_exposure_mapping(config)

        # Only 2 of the 4 eligible analyses should be processed
        assert mock_map.call_count == 2


# --- TestRunDigest ---


class TestRunDigest:
    @patch("worldlines.jobs._record_run")
    @patch("worldlines.jobs.generate_digest")
    def test_calls_generate_digest_with_correct_args(self, mock_gen, mock_record, tmp_path):
        config = _make_config(tmp_path)
        mock_gen.return_value = MagicMock(
            delivery_status="sent", error=None,
            digest_record={"item_count": 3},
        )

        with patch("worldlines.jobs.datetime") as mock_dt:
            fake_now = datetime(2025, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            run_digest(config)

        mock_gen.assert_called_once_with(
            "2025-06-15",
            "2025-06-15T00:00:00+00:00",
            until="2025-06-16T00:00:00+00:00",
            database_path=config.database_path,
            bot_token="test-token",
            chat_id="test-chat",
            api_key="test-key",
            model="test-model",
            parse_mode="HTML",
            max_items=20,
            max_retries=1,
        )

    @patch("worldlines.jobs._record_run")
    @patch("worldlines.jobs.generate_digest")
    def test_logs_delivery_status(self, mock_gen, mock_record, tmp_path):
        config = _make_config(tmp_path)
        mock_gen.return_value = MagicMock(
            delivery_status="empty_day", error=None,
            digest_record={"item_count": 0},
        )

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
    @patch("worldlines.jobs.run_temporal_linking")
    @patch("worldlines.jobs.run_exposure_mapping")
    @patch("worldlines.jobs.run_analysis")
    @patch("worldlines.jobs.run_ingestion")
    def test_calls_ingestion_analysis_exposure(self, mock_ingest, mock_analyze, mock_exposure, mock_temporal, tmp_path):
        config = _make_config(tmp_path)

        call_order = []
        mock_ingest.side_effect = lambda c: call_order.append("ingestion")
        mock_analyze.side_effect = lambda c: call_order.append("analysis")
        mock_exposure.side_effect = lambda c: call_order.append("exposure")
        mock_temporal.side_effect = lambda c: call_order.append("temporal_linking")

        run_pipeline(config)

        mock_ingest.assert_called_once_with(config)
        mock_analyze.assert_called_once_with(config)
        mock_exposure.assert_called_once_with(config)
        mock_temporal.assert_called_once_with(config)
        assert call_order == ["ingestion", "analysis", "exposure", "temporal_linking"]


# --- TestSendAlert ---


class TestSendAlert:
    @patch("worldlines.jobs.send_message")
    def test_sends_telegram_message(self, mock_send, tmp_path):
        config = _make_config(tmp_path)
        _send_alert(config, "Something broke")
        mock_send.assert_called_once_with(
            "test-token", "test-chat",
            "[WORLDLINES ALERT]\nSomething broke",
            parse_mode="", max_retries=2,
        )

    @patch("worldlines.jobs.send_message", side_effect=Exception("network error"))
    def test_never_raises(self, mock_send, tmp_path):
        config = _make_config(tmp_path)
        # Should not raise even if send_message fails
        _send_alert(config, "Something broke")


# --- TestAlertOnFailure ---


class TestAlertOnFailure:
    @patch("worldlines.jobs._send_alert")
    @patch("worldlines.jobs.get_adapter_class", side_effect=Exception("boom"))
    def test_ingestion_alerts_on_failure(self, mock_cls, mock_alert, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)
        run_ingestion(config)
        mock_alert.assert_called_once()
        assert "ingestion" in mock_alert.call_args[0][1].lower()

    @patch("worldlines.jobs._send_alert")
    @patch("worldlines.jobs._record_run")
    def test_analysis_alerts_on_top_level_failure(self, mock_record, mock_alert, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)
        with patch("worldlines.jobs.get_connection", side_effect=Exception("db fail")):
            run_analysis(config)
        mock_alert.assert_called_once()
        assert "analysis" in mock_alert.call_args[0][1].lower()

    @patch("worldlines.jobs._send_alert")
    @patch("worldlines.jobs._record_run")
    @patch("worldlines.jobs.generate_digest", side_effect=Exception("fail"))
    def test_digest_alerts_on_failure(self, mock_gen, mock_record, mock_alert, tmp_path):
        config = _make_config(tmp_path)
        run_digest(config)
        mock_alert.assert_called_once()
        assert "digest" in mock_alert.call_args[0][1].lower()

    @patch("worldlines.jobs._send_alert")
    @patch("worldlines.jobs._record_run")
    def test_exposure_alerts_on_top_level_failure(self, mock_record, mock_alert, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)
        with patch("worldlines.jobs.get_connection", side_effect=Exception("db fail")):
            run_exposure_mapping(config)
        mock_alert.assert_called_once()
        assert "exposure" in mock_alert.call_args[0][1].lower()


# --- TestSourceErrorTracking ---


class TestSourceErrorTracking:
    def test_record_source_failure_inserts_row(self, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        result = _record_source_failure(config.database_path, "rss", "connection refused")

        assert result == 1
        with get_connection(config.database_path) as conn:
            row = conn.execute(
                "SELECT consecutive_failures, last_error FROM source_errors WHERE adapter_name = ?",
                ("rss",),
            ).fetchone()
        assert row is not None
        assert row["consecutive_failures"] == 1
        assert row["last_error"] == "connection refused"

    def test_record_source_failure_increments_count(self, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        _record_source_failure(config.database_path, "rss", "error 1")
        result = _record_source_failure(config.database_path, "rss", "error 2")

        assert result == 2
        with get_connection(config.database_path) as conn:
            row = conn.execute(
                "SELECT consecutive_failures FROM source_errors WHERE adapter_name = ?",
                ("rss",),
            ).fetchone()
        assert row["consecutive_failures"] == 2

    def test_record_source_success_resets_count(self, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        _record_source_failure(config.database_path, "rss", "error 1")
        _record_source_failure(config.database_path, "rss", "error 2")
        _record_source_success(config.database_path, "rss")

        with get_connection(config.database_path) as conn:
            row = conn.execute(
                "SELECT consecutive_failures FROM source_errors WHERE adapter_name = ?",
                ("rss",),
            ).fetchone()
        assert row["consecutive_failures"] == 0

    def test_record_source_success_inserts_if_absent(self, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        _record_source_success(config.database_path, "hn")

        with get_connection(config.database_path) as conn:
            row = conn.execute(
                "SELECT consecutive_failures FROM source_errors WHERE adapter_name = ?",
                ("hn",),
            ).fetchone()
        assert row is not None
        assert row["consecutive_failures"] == 0


# --- TestIngestionStallDetection ---


def _seed_pipeline_run(conn, items_new: int, started_at: str) -> None:
    """Insert a fake ingestion pipeline_run record."""
    conn.execute(
        "INSERT INTO pipeline_runs (id, run_type, started_at, finished_at, status, result) "
        "VALUES (?, 'ingestion', ?, ?, 'success', ?)",
        (
            str(__import__("uuid").uuid4()),
            started_at,
            started_at,
            json.dumps({"items_new": items_new, "items_duplicate": 0}),
        ),
    )


class TestIngestionStallDetection:
    def test_stall_no_alert_insufficient_history(self, tmp_path):
        """Fewer than 3 runs in the window → no alert."""
        config = _make_config(tmp_path, ingestion_stall_hours=24, ingestion_stall_min_items=1)
        init_db(config.database_path)

        now = datetime.now(timezone.utc)
        # Only 2 runs
        with get_connection(config.database_path) as conn:
            _seed_pipeline_run(conn, 0, (now - timedelta(hours=2)).isoformat())
            _seed_pipeline_run(conn, 0, (now - timedelta(hours=1)).isoformat())

        with patch("worldlines.jobs._send_alert") as mock_alert:
            _check_ingestion_stall(config)
        mock_alert.assert_not_called()

    def test_stall_no_alert_items_above_threshold(self, tmp_path):
        """3 runs with sufficient items → no alert."""
        config = _make_config(tmp_path, ingestion_stall_hours=24, ingestion_stall_min_items=1)
        init_db(config.database_path)

        now = datetime.now(timezone.utc)
        with get_connection(config.database_path) as conn:
            _seed_pipeline_run(conn, 2, (now - timedelta(hours=3)).isoformat())
            _seed_pipeline_run(conn, 0, (now - timedelta(hours=2)).isoformat())
            _seed_pipeline_run(conn, 0, (now - timedelta(hours=1)).isoformat())

        with patch("worldlines.jobs._send_alert") as mock_alert:
            _check_ingestion_stall(config)
        mock_alert.assert_not_called()

    def test_stall_alert_sent(self, tmp_path):
        """3 runs, 0 items_new total, threshold=1 → alert sent."""
        config = _make_config(tmp_path, ingestion_stall_hours=24, ingestion_stall_min_items=1)
        init_db(config.database_path)

        now = datetime.now(timezone.utc)
        with get_connection(config.database_path) as conn:
            _seed_pipeline_run(conn, 0, (now - timedelta(hours=3)).isoformat())
            _seed_pipeline_run(conn, 0, (now - timedelta(hours=2)).isoformat())
            _seed_pipeline_run(conn, 0, (now - timedelta(hours=1)).isoformat())

        with patch("worldlines.jobs._send_alert") as mock_alert:
            _check_ingestion_stall(config)
        mock_alert.assert_called_once()
        assert "stall" in mock_alert.call_args[0][1].lower()


# --- TestAdapterFailureAlert ---


class TestAdapterFailureAlert:
    @patch("worldlines.jobs.ingest_item")
    @patch("worldlines.jobs.get_adapter_class")
    def test_adapter_failure_records_source_error(self, mock_get_cls, mock_ingest, tmp_path):
        config = _make_config(tmp_path)
        init_db(config.database_path)

        adapter_instance = MagicMock()
        adapter_instance.name = "rss"
        adapter_instance.fetch.side_effect = Exception("feed timeout")
        MockAdapter = MagicMock(return_value=adapter_instance)
        mock_get_cls.return_value = MockAdapter

        with patch("worldlines.jobs._send_alert"):
            run_ingestion(config)

        with get_connection(config.database_path) as conn:
            row = conn.execute(
                "SELECT consecutive_failures FROM source_errors WHERE adapter_name = ?",
                ("rss",),
            ).fetchone()
        assert row is not None
        assert row["consecutive_failures"] == 1

    @patch("worldlines.jobs.ingest_item")
    @patch("worldlines.jobs.get_adapter_class")
    def test_adapter_failure_no_alert_below_threshold(self, mock_get_cls, mock_ingest, tmp_path):
        """2nd consecutive failure is below default threshold of 3 → no alert."""
        config = _make_config(tmp_path, source_failure_alert_threshold=3)
        init_db(config.database_path)

        # Pre-seed 1 existing failure
        _record_source_failure(config.database_path, "rss", "previous error")

        adapter_instance = MagicMock()
        adapter_instance.name = "rss"
        adapter_instance.fetch.side_effect = Exception("another error")
        MockAdapter = MagicMock(return_value=adapter_instance)
        mock_get_cls.return_value = MockAdapter

        with patch("worldlines.jobs._send_alert") as mock_alert:
            run_ingestion(config)

        # Alert should not have been called for adapter failure (only 2 consecutive)
        adapter_alert_calls = [
            c for c in mock_alert.call_args_list
            if "consecutive" in c[0][1]
        ]
        assert len(adapter_alert_calls) == 0

    @patch("worldlines.jobs.ingest_item")
    @patch("worldlines.jobs.get_adapter_class")
    def test_adapter_failure_alert_at_threshold(self, mock_get_cls, mock_ingest, tmp_path):
        """3rd consecutive failure at threshold=3 → alert sent."""
        config = _make_config(tmp_path, source_failure_alert_threshold=3)
        init_db(config.database_path)

        # Pre-seed 2 existing failures
        _record_source_failure(config.database_path, "rss", "error 1")
        _record_source_failure(config.database_path, "rss", "error 2")

        adapter_instance = MagicMock()
        adapter_instance.name = "rss"
        adapter_instance.fetch.side_effect = Exception("error 3")
        MockAdapter = MagicMock(return_value=adapter_instance)
        mock_get_cls.return_value = MockAdapter

        with patch("worldlines.jobs._send_alert") as mock_alert:
            run_ingestion(config)

        adapter_alert_calls = [
            c for c in mock_alert.call_args_list
            if "consecutive" in c[0][1]
        ]
        assert len(adapter_alert_calls) == 1
        assert "rss" in adapter_alert_calls[0][0][1]

    @patch("worldlines.jobs.ingest_item")
    @patch("worldlines.jobs.get_adapter_class")
    def test_adapter_failure_continues_to_next_adapter(self, mock_get_cls, mock_ingest, tmp_path):
        """A failed adapter should not abort processing of remaining adapters."""
        sources = {
            "adapters": [
                {"type": "rss", "enabled": True, "feeds": []},
                {"type": "hn", "enabled": True},
            ]
        }
        config = _make_config(tmp_path, _sources=sources)
        init_db(config.database_path)

        failing_adapter = MagicMock()
        failing_adapter.name = "rss"
        failing_adapter.fetch.side_effect = Exception("rss down")

        passing_adapter = MagicMock()
        passing_adapter.name = "hn"
        passing_adapter.fetch.return_value = []

        mock_get_cls.side_effect = lambda t: (
            MagicMock(return_value=failing_adapter) if t == "rss"
            else MagicMock(return_value=passing_adapter)
        )

        with patch("worldlines.jobs._send_alert"):
            run_ingestion(config)

        passing_adapter.fetch.assert_called_once()

    @patch("worldlines.jobs.ingest_item")
    @patch("worldlines.jobs.get_adapter_class")
    def test_adapter_success_resets_failures(self, mock_get_cls, mock_ingest, tmp_path):
        """A successful fetch after failures resets consecutive_failures to 0."""
        config = _make_config(tmp_path)
        init_db(config.database_path)

        # Pre-seed 2 failures
        _record_source_failure(config.database_path, "rss", "old error")
        _record_source_failure(config.database_path, "rss", "old error 2")

        adapter_instance = MagicMock()
        adapter_instance.name = "rss"
        adapter_instance.fetch.return_value = []
        MockAdapter = MagicMock(return_value=adapter_instance)
        mock_get_cls.return_value = MockAdapter

        mock_ingest.return_value = MagicMock(status="new")

        with patch("worldlines.jobs._send_alert"):
            run_ingestion(config)

        with get_connection(config.database_path) as conn:
            row = conn.execute(
                "SELECT consecutive_failures FROM source_errors WHERE adapter_name = ?",
                ("rss",),
            ).fetchone()
        assert row["consecutive_failures"] == 0
