"""RSS/Atom feed source adapter."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape

import feedparser
import httpx

from worldlines.ingestion.adapter import SourceAdapter
from worldlines.ingestion.normalize import RawSourceItem
from worldlines.storage.connection import get_connection

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    return unescape(_HTML_TAG_RE.sub("", text)).strip()


def _parse_pub_date(entry: dict) -> str | None:
    """Extract and normalize the publication date from a feed entry."""
    raw = entry.get("published") or entry.get("updated")
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            return dt.isoformat()
        except (ValueError, TypeError):
            pass
    # feedparser sometimes provides a parsed tuple
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            dt = datetime(*parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except (ValueError, TypeError):
            pass
    return None


def _get_content(entry: dict) -> str:
    """Extract the best available content from a feed entry."""
    # Prefer content:encoded (full article), then summary/description
    if "content" in entry and entry["content"]:
        # feedparser puts content:encoded in entry.content[0].value
        return strip_html(entry["content"][0].get("value", ""))
    return strip_html(entry.get("summary", "") or entry.get("description", ""))


class RSSAdapter(SourceAdapter):
    """Adapter for RSS and Atom feeds."""

    def __init__(self, database_path: str, max_items_per_feed: int = 50) -> None:
        self._database_path = database_path
        self._max_items_per_feed = max_items_per_feed
        self._feeds: list[dict] = []

    @property
    def name(self) -> str:
        return "rss"

    def configure(self, config: dict) -> None:
        """Accept feed configuration.

        Expected format:
        {
            "feeds": [
                {"url": "...", "source_name": "...", "source_type": "..."},
                ...
            ]
        }
        """
        self._feeds = config.get("feeds", [])

    def fetch(self) -> list[RawSourceItem]:
        """Fetch new items from all configured feeds."""
        all_items: list[RawSourceItem] = []
        for feed_config in self._feeds:
            try:
                items = self._fetch_feed(feed_config)
                all_items.extend(items)
            except Exception:
                logger.exception(
                    "Failed to fetch feed %s", feed_config.get("url", "unknown")
                )
        return all_items

    def _fetch_feed(self, feed_config: dict) -> list[RawSourceItem]:
        """Fetch and parse a single RSS/Atom feed."""
        url = feed_config["url"]
        source_name = feed_config["source_name"]
        source_type = feed_config.get("source_type", "news")

        seen_urls = self._load_seen_urls(url)

        try:
            response = httpx.get(url, timeout=30, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("HTTP error fetching %s", url)
            return []

        feed = feedparser.parse(response.text)
        items: list[RawSourceItem] = []

        for entry in feed.entries[: self._max_items_per_feed]:
            entry_url = entry.get("link")

            if entry_url and entry_url in seen_urls:
                continue

            title = entry.get("title", "").strip()
            content = _get_content(entry)

            if not title or not content:
                logger.debug("Skipping entry with missing title or content: %s", entry_url)
                continue

            items.append(
                RawSourceItem(
                    source_name=source_name,
                    source_type=source_type,
                    title=title,
                    content=content,
                    url=entry_url,
                    published_at=_parse_pub_date(entry),
                )
            )

            if entry_url:
                seen_urls.add(entry_url)

        self._save_seen_urls(url, seen_urls)
        logger.info("Fetched %d new items from %s", len(items), source_name)
        return items

    def _load_seen_urls(self, feed_url: str) -> set[str]:
        """Load the set of previously seen URLs for a feed."""
        with get_connection(self._database_path) as conn:
            row = conn.execute(
                "SELECT state_data FROM adapter_state "
                "WHERE adapter_name = ? AND feed_url = ?",
                (self.name, feed_url),
            ).fetchone()
        if row is None:
            return set()
        data = json.loads(row["state_data"])
        return set(data.get("seen_urls", []))

    def _save_seen_urls(self, feed_url: str, seen_urls: set[str]) -> None:
        """Persist the set of seen URLs for a feed."""
        state_data = json.dumps({"seen_urls": sorted(seen_urls)})
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self._database_path) as conn:
            conn.execute(
                "INSERT INTO adapter_state (adapter_name, feed_url, state_data, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(adapter_name, feed_url) DO UPDATE SET "
                "state_data = excluded.state_data, updated_at = excluded.updated_at",
                (self.name, feed_url, state_data, now),
            )
