"""Tests for worldlines.ingestion.earnings_adapter — Earnings transcript adapter."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from worldlines.ingestion.earnings_adapter import EarningsAdapter
from worldlines.storage.connection import get_connection
from worldlines.storage.schema import init_db


def _make_transcript(quarter=4, year=2025, date="2025-12-15", content="Earnings content here"):
    return {
        "quarter": quarter,
        "year": year,
        "date": date,
        "content": content,
    }


class TestEarningsAdapter:
    def test_fetches_transcripts(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = EarningsAdapter(db_path)
        with patch.dict("os.environ", {"FMP_API_KEY": "test-key"}):
            adapter.configure({"tickers": ["NVDA"], "api_key_env": "FMP_API_KEY"})

        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = [_make_transcript()]

        with patch("worldlines.ingestion.earnings_adapter.httpx.get", return_value=resp):
            result = adapter.fetch()

        assert len(result) == 1
        assert result[0].title == "NVDA Q4 2025 Earnings Call"
        assert result[0].source_type == "transcript"
        assert result[0].source_name == "NVDA Earnings"

    def test_truncates_long_content(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = EarningsAdapter(db_path)
        with patch.dict("os.environ", {"FMP_API_KEY": "test-key"}):
            adapter.configure({"tickers": ["NVDA"], "api_key_env": "FMP_API_KEY", "max_content_chars": 100})

        long_content = "A" * 500
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = [_make_transcript(content=long_content)]

        with patch("worldlines.ingestion.earnings_adapter.httpx.get", return_value=resp):
            result = adapter.fetch()

        assert len(result) == 1
        assert len(result[0].content) == 100

    def test_daily_throttle(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Pre-seed state with a recent fetch
        now = datetime.now(timezone.utc)
        state = {
            "NVDA": {
                "last_fetch_at": now.isoformat(),
                "last_transcript_date": "2025-12-15",
            }
        }
        with get_connection(db_path) as conn:
            conn.execute(
                "INSERT INTO adapter_state (adapter_name, feed_url, state_data, updated_at) "
                "VALUES (?, ?, ?, ?)",
                ("earnings", "earnings", json.dumps(state), now.isoformat()),
            )

        adapter = EarningsAdapter(db_path)
        with patch.dict("os.environ", {"FMP_API_KEY": "test-key"}):
            adapter.configure({"tickers": ["NVDA"], "api_key_env": "FMP_API_KEY"})

        with patch("worldlines.ingestion.earnings_adapter.httpx.get") as mock_get:
            result = adapter.fetch()

        # Should not make any HTTP calls due to throttle
        mock_get.assert_not_called()
        assert len(result) == 0

    def test_skips_already_seen_transcript(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Pre-seed state with old fetch time but same transcript date
        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        state = {
            "NVDA": {
                "last_fetch_at": old_time,
                "last_transcript_date": "2025-12-15",
            }
        }
        with get_connection(db_path) as conn:
            conn.execute(
                "INSERT INTO adapter_state (adapter_name, feed_url, state_data, updated_at) "
                "VALUES (?, ?, ?, ?)",
                ("earnings", "earnings", json.dumps(state), old_time),
            )

        adapter = EarningsAdapter(db_path)
        with patch.dict("os.environ", {"FMP_API_KEY": "test-key"}):
            adapter.configure({"tickers": ["NVDA"], "api_key_env": "FMP_API_KEY"})

        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = [_make_transcript(date="2025-12-15")]

        with patch("worldlines.ingestion.earnings_adapter.httpx.get", return_value=resp):
            result = adapter.fetch()

        assert len(result) == 0

    def test_missing_api_key_returns_empty(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = EarningsAdapter(db_path)
        with patch.dict("os.environ", {}, clear=True):
            adapter.configure({"tickers": ["NVDA"], "api_key_env": "FMP_API_KEY"})

        result = adapter.fetch()
        assert result == []

    def test_handles_api_error(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = EarningsAdapter(db_path)
        with patch.dict("os.environ", {"FMP_API_KEY": "test-key"}):
            adapter.configure({"tickers": ["NVDA", "AMD"], "api_key_env": "FMP_API_KEY"})

        import httpx as httpx_mod

        call_count = 0

        def side_effect(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx_mod.ConnectError("fail")
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = [_make_transcript(content="AMD earnings")]
            return resp

        with patch("worldlines.ingestion.earnings_adapter.httpx.get", side_effect=side_effect):
            result = adapter.fetch()

        # NVDA failed, AMD succeeded
        assert len(result) == 1
        assert "AMD" in result[0].title

    def test_empty_api_response(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = EarningsAdapter(db_path)
        with patch.dict("os.environ", {"FMP_API_KEY": "test-key"}):
            adapter.configure({"tickers": ["NVDA"], "api_key_env": "FMP_API_KEY"})

        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = []

        with patch("worldlines.ingestion.earnings_adapter.httpx.get", return_value=resp):
            result = adapter.fetch()

        assert len(result) == 0

    def test_multiple_tickers(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = EarningsAdapter(db_path)
        with patch.dict("os.environ", {"FMP_API_KEY": "test-key"}):
            adapter.configure({"tickers": ["NVDA", "AMD"], "api_key_env": "FMP_API_KEY"})

        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = [_make_transcript()]

        with patch("worldlines.ingestion.earnings_adapter.httpx.get", return_value=resp):
            result = adapter.fetch()

        assert len(result) == 2
        tickers_in_titles = {item.title.split()[0] for item in result}
        assert tickers_in_titles == {"NVDA", "AMD"}
