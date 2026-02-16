"""Hacker News source adapter — fetches top stories above a score threshold."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

import httpx

from worldlines.ingestion.adapter import SourceAdapter
from worldlines.ingestion.normalize import RawSourceItem
from worldlines.storage.connection import get_connection

logger = logging.getLogger(__name__)

_HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
_HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
_MAX_SEEN_IDS = 5000
_FETCH_DELAY = 0.1  # seconds between item fetches


class HNAdapter(SourceAdapter):
    """Adapter for Hacker News top stories."""

    def __init__(self, database_path: str, max_items_per_source: int = 50) -> None:
        self._database_path = database_path
        self._max_items_per_source = max_items_per_source
        self._min_score = 100
        self._max_items = 30

    @property
    def name(self) -> str:
        return "hn"

    def configure(self, config: dict) -> None:
        self._min_score = config.get("min_score", 100)
        self._max_items = config.get("max_items", 30)

    def fetch(self) -> list[RawSourceItem]:
        seen_ids = self._load_seen_ids()
        items: list[RawSourceItem] = []

        try:
            resp = httpx.get(_HN_TOP_URL, timeout=30)
            resp.raise_for_status()
            story_ids = resp.json()
        except (httpx.HTTPError, ValueError):
            logger.exception("Failed to fetch HN top stories")
            return []

        for story_id in story_ids:
            if len(items) >= self._max_items:
                break
            if story_id in seen_ids:
                continue

            try:
                time.sleep(_FETCH_DELAY)
                item_resp = httpx.get(_HN_ITEM_URL.format(story_id), timeout=15)
                item_resp.raise_for_status()
                data = item_resp.json()
            except (httpx.HTTPError, ValueError):
                logger.warning("Failed to fetch HN item %s", story_id)
                continue

            if not data or data.get("type") != "story":
                seen_ids.add(story_id)
                continue

            score = data.get("score", 0)
            if score < self._min_score:
                continue

            title = data.get("title", "").strip()
            if not title:
                seen_ids.add(story_id)
                continue

            url = data.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
            published_at = None
            if data.get("time"):
                published_at = datetime.fromtimestamp(
                    data["time"], tz=timezone.utc
                ).isoformat()

            items.append(
                RawSourceItem(
                    source_name="Hacker News",
                    source_type="news",
                    title=title,
                    content=title,
                    url=url,
                    published_at=published_at,
                )
            )
            seen_ids.add(story_id)

        self._save_seen_ids(seen_ids)
        logger.info("Fetched %d new items from Hacker News", len(items))
        return items

    def _load_seen_ids(self) -> set[int]:
        with get_connection(self._database_path) as conn:
            row = conn.execute(
                "SELECT state_data FROM adapter_state "
                "WHERE adapter_name = ? AND feed_url = ?",
                (self.name, "topstories"),
            ).fetchone()
        if row is None:
            return set()
        data = json.loads(row["state_data"])
        return set(data.get("seen_ids", []))

    def _save_seen_ids(self, seen_ids: set[int]) -> None:
        # Cap to most recent IDs to prevent unbounded growth
        capped = sorted(seen_ids, reverse=True)[:_MAX_SEEN_IDS]
        state_data = json.dumps({"seen_ids": capped})
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self._database_path) as conn:
            conn.execute(
                "INSERT INTO adapter_state (adapter_name, feed_url, state_data, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(adapter_name, feed_url) DO UPDATE SET "
                "state_data = excluded.state_data, updated_at = excluded.updated_at",
                (self.name, "topstories", state_data, now),
            )
