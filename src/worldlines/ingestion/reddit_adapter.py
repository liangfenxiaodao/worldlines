"""Reddit source adapter — fetches top posts from configured subreddits."""

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

_REDDIT_TOP_URL = "https://www.reddit.com/r/{}/top.json"
_USER_AGENT = "Worldlines/0.1 (trend-intelligence)"
_MAX_SEEN_IDS = 5000
_FETCH_DELAY = 0.5  # seconds between subreddit fetches


class RedditAdapter(SourceAdapter):
    """Adapter for Reddit subreddit top posts."""

    def __init__(self, database_path: str, max_items_per_source: int = 50) -> None:
        self._database_path = database_path
        self._max_items_per_source = max_items_per_source
        self._subreddits: list[dict] = []

    @property
    def name(self) -> str:
        return "reddit"

    def configure(self, config: dict) -> None:
        self._subreddits = config.get("subreddits", [])

    def fetch(self) -> list[RawSourceItem]:
        all_items: list[RawSourceItem] = []
        for i, sub_config in enumerate(self._subreddits):
            if i > 0:
                time.sleep(_FETCH_DELAY)
            try:
                items = self._fetch_subreddit(sub_config)
                all_items.extend(items)
            except Exception:
                logger.exception(
                    "Failed to fetch subreddit r/%s",
                    sub_config.get("name", "unknown"),
                )
        return all_items

    def _fetch_subreddit(self, sub_config: dict) -> list[RawSourceItem]:
        subreddit = sub_config["name"]
        source_type = sub_config.get("source_type", "news")
        min_score = sub_config.get("min_score", 50)
        limit = sub_config.get("limit", 25)

        seen_ids = self._load_seen_ids(subreddit)
        url = _REDDIT_TOP_URL.format(subreddit)

        try:
            resp = httpx.get(
                url,
                params={"t": "day", "limit": limit},
                headers={"User-Agent": _USER_AGENT},
                timeout=30,
                follow_redirects=True,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            logger.exception("Failed to fetch Reddit r/%s", subreddit)
            return []

        posts = data.get("data", {}).get("children", [])
        items: list[RawSourceItem] = []

        for post_wrapper in posts:
            if len(items) >= self._max_items_per_source:
                break

            post = post_wrapper.get("data", {})
            post_id = post.get("id", "")

            if post_id in seen_ids:
                continue

            score = post.get("score", 0)
            if score < min_score:
                seen_ids.add(post_id)
                continue

            title = post.get("title", "").strip()
            if not title:
                seen_ids.add(post_id)
                continue

            selftext = post.get("selftext", "").strip()
            content = f"{title}\n\n{selftext}" if selftext else title

            published_at = None
            created_utc = post.get("created_utc")
            if created_utc:
                published_at = datetime.fromtimestamp(
                    created_utc, tz=timezone.utc
                ).isoformat()

            post_url = post.get("url") or f"https://www.reddit.com{post.get('permalink', '')}"

            items.append(
                RawSourceItem(
                    source_name=f"Reddit r/{subreddit}",
                    source_type=source_type,
                    title=title,
                    content=content,
                    url=post_url,
                    published_at=published_at,
                )
            )
            seen_ids.add(post_id)

        self._save_seen_ids(subreddit, seen_ids)
        logger.info("Fetched %d new items from Reddit r/%s", len(items), subreddit)
        return items

    def _load_seen_ids(self, subreddit: str) -> set[str]:
        with get_connection(self._database_path) as conn:
            row = conn.execute(
                "SELECT state_data FROM adapter_state "
                "WHERE adapter_name = ? AND feed_url = ?",
                (self.name, subreddit),
            ).fetchone()
        if row is None:
            return set()
        data = json.loads(row["state_data"])
        return set(data.get("seen_ids", []))

    def _save_seen_ids(self, subreddit: str, seen_ids: set[str]) -> None:
        capped = sorted(seen_ids, reverse=True)[:_MAX_SEEN_IDS]
        state_data = json.dumps({"seen_ids": capped})
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self._database_path) as conn:
            conn.execute(
                "INSERT INTO adapter_state (adapter_name, feed_url, state_data, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(adapter_name, feed_url) DO UPDATE SET "
                "state_data = excluded.state_data, updated_at = excluded.updated_at",
                (self.name, subreddit, state_data, now),
            )
