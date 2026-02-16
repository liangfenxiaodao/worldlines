"""Earnings transcript adapter — fetches earnings call transcripts from FMP API."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx

from worldlines.ingestion.adapter import SourceAdapter
from worldlines.ingestion.normalize import RawSourceItem
from worldlines.storage.connection import get_connection

logger = logging.getLogger(__name__)

_FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"
_THROTTLE_HOURS = 24


class EarningsAdapter(SourceAdapter):
    """Adapter for earnings call transcripts via Financial Modeling Prep API."""

    def __init__(self, database_path: str, max_items_per_source: int = 50) -> None:
        self._database_path = database_path
        self._max_items_per_source = max_items_per_source
        self._tickers: list[str] = []
        self._api_key: str | None = None
        self._max_content_chars = 8000

    @property
    def name(self) -> str:
        return "earnings"

    def configure(self, config: dict) -> None:
        self._tickers = config.get("tickers", [])
        self._max_content_chars = config.get("max_content_chars", 8000)
        api_key_env = config.get("api_key_env", "FMP_API_KEY")
        self._api_key = os.environ.get(api_key_env)
        if not self._api_key:
            logger.warning("No API key found in env var '%s'; earnings adapter disabled", api_key_env)

    def fetch(self) -> list[RawSourceItem]:
        if not self._api_key:
            return []

        items: list[RawSourceItem] = []
        state = self._load_state()
        now = datetime.now(timezone.utc)

        for ticker in self._tickers:
            ticker_state = state.get(ticker, {})
            last_fetch = ticker_state.get("last_fetch_at")
            if last_fetch:
                last_dt = datetime.fromisoformat(last_fetch)
                if now - last_dt < timedelta(hours=_THROTTLE_HOURS):
                    continue

            try:
                transcript = self._fetch_transcript(ticker)
            except Exception:
                logger.exception("Failed to fetch transcript for %s", ticker)
                continue

            if transcript is None:
                # No new transcript; update fetch time to avoid re-checking
                state[ticker] = {
                    "last_fetch_at": now.isoformat(),
                    "last_transcript_date": ticker_state.get("last_transcript_date"),
                }
                continue

            quarter = transcript.get("quarter", "?")
            year = transcript.get("year", "?")
            date_str = transcript.get("date", "")
            content = transcript.get("content", "")

            # Skip if we already have this transcript
            if date_str and date_str == ticker_state.get("last_transcript_date"):
                state[ticker] = {
                    "last_fetch_at": now.isoformat(),
                    "last_transcript_date": date_str,
                }
                continue

            if content and len(content) > self._max_content_chars:
                content = content[: self._max_content_chars]

            if not content.strip():
                state[ticker] = {
                    "last_fetch_at": now.isoformat(),
                    "last_transcript_date": date_str or ticker_state.get("last_transcript_date"),
                }
                continue

            title = f"{ticker} Q{quarter} {year} Earnings Call"

            published_at = None
            if date_str:
                try:
                    published_at = datetime.fromisoformat(date_str).isoformat()
                except ValueError:
                    pass

            items.append(
                RawSourceItem(
                    source_name=f"{ticker} Earnings",
                    source_type="transcript",
                    title=title,
                    content=content,
                    url=None,
                    published_at=published_at,
                )
            )

            state[ticker] = {
                "last_fetch_at": now.isoformat(),
                "last_transcript_date": date_str or ticker_state.get("last_transcript_date"),
            }

        self._save_state(state)
        logger.info("Fetched %d new earnings transcripts", len(items))
        return items

    def _fetch_transcript(self, ticker: str) -> dict | None:
        """Fetch the most recent transcript for a ticker. Returns None if unavailable."""
        url = f"{_FMP_BASE_URL}/earning_call_transcript/{ticker}"
        resp = httpx.get(url, params={"apikey": self._api_key}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data or not isinstance(data, list):
            return None
        return data[0]

    def _load_state(self) -> dict:
        with get_connection(self._database_path) as conn:
            row = conn.execute(
                "SELECT state_data FROM adapter_state "
                "WHERE adapter_name = ? AND feed_url = ?",
                (self.name, "earnings"),
            ).fetchone()
        if row is None:
            return {}
        return json.loads(row["state_data"])

    def _save_state(self, state: dict) -> None:
        state_data = json.dumps(state)
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self._database_path) as conn:
            conn.execute(
                "INSERT INTO adapter_state (adapter_name, feed_url, state_data, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(adapter_name, feed_url) DO UPDATE SET "
                "state_data = excluded.state_data, updated_at = excluded.updated_at",
                (self.name, "earnings", state_data, now),
            )
