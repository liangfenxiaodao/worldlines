"""Ingestion pipeline — source fetching, normalization, and deduplication."""

from worldlines.ingestion.github_adapter import GitHubTrendingAdapter
from worldlines.ingestion.hn_adapter import HNAdapter
from worldlines.ingestion.reddit_adapter import RedditAdapter
from worldlines.ingestion.registry import register_adapter
from worldlines.ingestion.rss_adapter import RSSAdapter

register_adapter("rss", RSSAdapter)
register_adapter("hn", HNAdapter)
register_adapter("reddit", RedditAdapter)
register_adapter("github", GitHubTrendingAdapter)
