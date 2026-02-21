"""GitHub Trending source adapter — fetches trending repos via GitHub Search API."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import httpx

from worldlines.ingestion.adapter import SourceAdapter
from worldlines.ingestion.normalize import RawSourceItem
from worldlines.storage.connection import get_connection

logger = logging.getLogger(__name__)

_GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
_MAX_SEEN_IDS = 5000
_FETCH_DELAY = 2.0  # seconds between language searches


class GitHubTrendingAdapter(SourceAdapter):
    """Adapter for GitHub trending repositories via the Search API."""

    def __init__(self, database_path: str, max_items_per_source: int = 50) -> None:
        self._database_path = database_path
        self._max_items_per_source = max_items_per_source
        self._languages: list[str] = []
        self._min_stars = 100
        self._time_window_days = 7
        self._max_items = 20
        self._source_type = "industry"

    @property
    def name(self) -> str:
        return "github"

    def configure(self, config: dict) -> None:
        self._languages = config.get("languages", [])
        self._min_stars = config.get("min_stars", 100)
        self._time_window_days = config.get("time_window_days", 7)
        self._max_items = config.get("max_items", 20)
        self._source_type = config.get("source_type", "industry")

    def fetch(self) -> list[RawSourceItem]:
        seen_ids = self._load_seen_ids()
        all_items: list[RawSourceItem] = []
        token = os.environ.get("GITHUB_TOKEN")

        headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        for i, language in enumerate(self._languages):
            if len(all_items) >= self._max_items:
                break
            if i > 0:
                time.sleep(_FETCH_DELAY)
            try:
                items = self._fetch_language(language, headers, seen_ids)
                all_items.extend(items)
            except Exception:
                logger.exception("Failed to fetch GitHub trending for %s", language)

        self._save_seen_ids(seen_ids)
        all_items = all_items[: self._max_items]
        logger.info("Fetched %d new items from GitHub Trending", len(all_items))
        return all_items

    def _fetch_language(
        self,
        language: str,
        headers: dict[str, str],
        seen_ids: set[int],
    ) -> list[RawSourceItem]:
        since_date = (
            datetime.now(timezone.utc) - timedelta(days=self._time_window_days)
        ).strftime("%Y-%m-%d")

        query = f"stars:>{self._min_stars} pushed:>{since_date}"
        if language:
            query += f" language:{language}"

        per_page = min(30, self._max_items)

        try:
            resp = httpx.get(
                _GITHUB_SEARCH_URL,
                params={
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": per_page,
                },
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()

            remaining = resp.headers.get("X-RateLimit-Remaining")
            if remaining is not None and int(remaining) <= 1:
                logger.warning(
                    "GitHub API rate limit nearly exhausted (%s remaining), stopping",
                    remaining,
                )
                return []

            data = resp.json()
        except (httpx.HTTPError, ValueError):
            logger.exception("Failed GitHub search for language=%s", language)
            return []

        repos = data.get("items", [])
        items: list[RawSourceItem] = []

        for repo in repos:
            repo_id = repo.get("id")
            if repo_id is None:
                continue
            if repo_id in seen_ids:
                continue

            full_name = repo.get("full_name", "")
            description = repo.get("description") or ""
            lang = repo.get("language") or "Unknown"
            stars = repo.get("stargazers_count", 0)

            if not full_name.strip() or len(description) < 20:
                seen_ids.add(repo_id)
                continue

            content = f"{description} | {lang} | {stars} stars"
            published_at = repo.get("pushed_at")

            items.append(
                RawSourceItem(
                    source_name="GitHub Trending",
                    source_type=self._source_type,
                    title=full_name,
                    content=content,
                    url=repo.get("html_url"),
                    published_at=published_at,
                )
            )
            seen_ids.add(repo_id)

        return items

    def _load_seen_ids(self) -> set[int]:
        with get_connection(self._database_path) as conn:
            row = conn.execute(
                "SELECT state_data FROM adapter_state "
                "WHERE adapter_name = ? AND feed_url = ?",
                (self.name, "search"),
            ).fetchone()
        if row is None:
            return set()
        data = json.loads(row["state_data"])
        return set(data.get("seen_ids", []))

    def _save_seen_ids(self, seen_ids: set[int]) -> None:
        capped = sorted(seen_ids, reverse=True)[:_MAX_SEEN_IDS]
        state_data = json.dumps({"seen_ids": capped})
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self._database_path) as conn:
            conn.execute(
                "INSERT INTO adapter_state (adapter_name, feed_url, state_data, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(adapter_name, feed_url) DO UPDATE SET "
                "state_data = excluded.state_data, updated_at = excluded.updated_at",
                (self.name, "search", state_data, now),
            )
