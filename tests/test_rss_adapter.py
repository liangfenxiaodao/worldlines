"""Tests for worldlines.ingestion.rss_adapter — RSS/Atom source adapter."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from worldlines.ingestion.normalize import RawSourceItem, ingest_item
from worldlines.ingestion.rss_adapter import (
    RSSAdapter,
    strip_html,
    _get_content,
    _parse_pub_date,
)
from worldlines.storage.connection import get_connection
from worldlines.storage.schema import init_db

# --- Sample feed XML ---

SAMPLE_RSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Article One</title>
      <link>https://example.com/article-1</link>
      <description>&lt;p&gt;First article content.&lt;/p&gt;</description>
      <pubDate>Sat, 15 Jun 2025 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Article Two</title>
      <link>https://example.com/article-2</link>
      <description>Second article content.</description>
      <pubDate>Sat, 15 Jun 2025 11:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Article Three</title>
      <link>https://example.com/article-3</link>
      <description>Third article content.</description>
      <pubDate>Sat, 15 Jun 2025 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

SAMPLE_ATOM = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>Atom Article</title>
    <link href="https://example.com/atom-1"/>
    <summary>Atom content body.</summary>
    <updated>2025-06-15T10:00:00Z</updated>
  </entry>
</feed>
"""

EMPTY_RSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Empty Feed</title>
  </channel>
</rss>
"""


@pytest.fixture()
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def _mock_get(url, **kwargs):
    """Mock httpx.get returning sample RSS."""

    class MockResponse:
        status_code = 200
        text = SAMPLE_RSS

        def raise_for_status(self):
            pass

    return MockResponse()


def _make_adapter(db_path, feeds=None):
    """Create and configure an RSSAdapter."""
    adapter = RSSAdapter(database_path=db_path)
    adapter.configure({
        "feeds": feeds or [
            {
                "url": "https://example.com/feed.xml",
                "source_name": "Test Source",
                "source_type": "news",
            }
        ]
    })
    return adapter


# --- Helper functions ---


class TestStripHtml:
    def test_removes_tags(self):
        assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_unescapes_entities(self):
        assert strip_html("&amp; &lt; &gt;") == "& < >"

    def test_plain_text_unchanged(self):
        assert strip_html("plain text") == "plain text"

    def test_strips_whitespace(self):
        assert strip_html("  hello  ") == "hello"


class TestParsePubDate:
    def test_rfc2822_date(self):
        entry = {"published": "Sat, 15 Jun 2025 10:00:00 GMT"}
        result = _parse_pub_date(entry)
        assert result is not None
        assert "2025-06-15" in result

    def test_uses_updated_as_fallback(self):
        entry = {"updated": "Sat, 15 Jun 2025 10:00:00 GMT"}
        result = _parse_pub_date(entry)
        assert result is not None

    def test_returns_none_if_missing(self):
        assert _parse_pub_date({}) is None

    def test_parsed_tuple_fallback(self):
        # feedparser provides parsed tuples
        entry = {"published_parsed": (2025, 6, 15, 10, 0, 0, 5, 166, 0)}
        result = _parse_pub_date(entry)
        assert result is not None
        assert "2025-06-15" in result


class TestGetContent:
    def test_prefers_content_encoded(self):
        entry = {
            "content": [{"value": "<p>Full article</p>"}],
            "summary": "Short summary",
        }
        assert _get_content(entry) == "Full article"

    def test_falls_back_to_summary(self):
        entry = {"summary": "<p>Summary text</p>"}
        assert _get_content(entry) == "Summary text"

    def test_falls_back_to_description(self):
        entry = {"description": "Description text"}
        assert _get_content(entry) == "Description text"

    def test_returns_empty_if_nothing(self):
        assert _get_content({}) == ""


# --- RSSAdapter ---


class TestRSSAdapter:
    def test_name(self, db_path):
        adapter = RSSAdapter(database_path=db_path)
        assert adapter.name == "rss"

    @patch("worldlines.ingestion.rss_adapter.httpx.get", side_effect=_mock_get)
    def test_fetches_items(self, mock_get, db_path):
        adapter = _make_adapter(db_path)
        items = adapter.fetch()
        assert len(items) == 3
        assert all(isinstance(i, RawSourceItem) for i in items)

    @patch("worldlines.ingestion.rss_adapter.httpx.get", side_effect=_mock_get)
    def test_item_fields(self, mock_get, db_path):
        adapter = _make_adapter(db_path)
        items = adapter.fetch()
        item = items[0]
        assert item.title == "Article One"
        assert item.source_name == "Test Source"
        assert item.source_type == "news"
        assert item.url == "https://example.com/article-1"
        assert item.content == "First article content."
        assert item.published_at is not None

    @patch("worldlines.ingestion.rss_adapter.httpx.get", side_effect=_mock_get)
    def test_strips_html_from_content(self, mock_get, db_path):
        adapter = _make_adapter(db_path)
        items = adapter.fetch()
        # First item has <p> tags in description
        assert "<p>" not in items[0].content

    @patch("worldlines.ingestion.rss_adapter.httpx.get", side_effect=_mock_get)
    def test_skips_seen_urls_on_second_fetch(self, mock_get, db_path):
        adapter = _make_adapter(db_path)
        first = adapter.fetch()
        assert len(first) == 3

        second = adapter.fetch()
        assert len(second) == 0

    @patch("worldlines.ingestion.rss_adapter.httpx.get", side_effect=_mock_get)
    def test_state_persists_across_instances(self, mock_get, db_path):
        adapter1 = _make_adapter(db_path)
        adapter1.fetch()

        # New adapter instance, same DB
        adapter2 = _make_adapter(db_path)
        items = adapter2.fetch()
        assert len(items) == 0

    @patch("worldlines.ingestion.rss_adapter.httpx.get", side_effect=_mock_get)
    def test_max_items_per_feed(self, mock_get, db_path):
        adapter = RSSAdapter(database_path=db_path, max_items_per_feed=2)
        adapter.configure({
            "feeds": [{
                "url": "https://example.com/feed.xml",
                "source_name": "Test",
                "source_type": "news",
            }]
        })
        items = adapter.fetch()
        assert len(items) == 2

    def test_handles_http_error_gracefully(self, db_path):
        import httpx as httpx_mod

        def mock_error(url, **kwargs):
            raise httpx_mod.HTTPError("Connection failed")

        adapter = _make_adapter(db_path)
        with patch("worldlines.ingestion.rss_adapter.httpx.get", side_effect=mock_error):
            items = adapter.fetch()
        assert items == []

    @patch("worldlines.ingestion.rss_adapter.httpx.get")
    def test_empty_feed(self, mock_get, db_path):
        class MockResponse:
            status_code = 200
            text = EMPTY_RSS
            def raise_for_status(self):
                pass

        mock_get.return_value = MockResponse()
        adapter = _make_adapter(db_path)
        items = adapter.fetch()
        assert items == []

    @patch("worldlines.ingestion.rss_adapter.httpx.get")
    def test_atom_feed(self, mock_get, db_path):
        class MockResponse:
            status_code = 200
            text = SAMPLE_ATOM
            def raise_for_status(self):
                pass

        mock_get.return_value = MockResponse()
        adapter = _make_adapter(db_path)
        items = adapter.fetch()
        assert len(items) == 1
        assert items[0].title == "Atom Article"
        assert items[0].content == "Atom content body."

    @patch("worldlines.ingestion.rss_adapter.httpx.get", side_effect=_mock_get)
    def test_multiple_feeds(self, mock_get, db_path):
        adapter = _make_adapter(db_path, feeds=[
            {"url": "https://example.com/feed1.xml", "source_name": "Source A", "source_type": "news"},
            {"url": "https://example.com/feed2.xml", "source_name": "Source B", "source_type": "news"},
        ])
        items = adapter.fetch()
        # 3 items from each feed
        assert len(items) == 6
        source_names = {i.source_name for i in items}
        assert source_names == {"Source A", "Source B"}


# --- End-to-end: adapter → ingest ---


class TestEndToEnd:
    @patch("worldlines.ingestion.rss_adapter.httpx.get", side_effect=_mock_get)
    def test_adapter_items_flow_through_ingest(self, mock_get, db_path):
        adapter = _make_adapter(db_path)
        items = adapter.fetch()

        results = [ingest_item(item, db_path) for item in items]
        new_count = sum(1 for r in results if r.status == "new")
        assert new_count == 3

        with get_connection(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        assert count == 3

    @patch("worldlines.ingestion.rss_adapter.httpx.get", side_effect=_mock_get)
    def test_duplicate_items_detected_on_reingest(self, mock_get, db_path):
        adapter = _make_adapter(db_path)
        items = adapter.fetch()

        # Ingest all items
        for item in items:
            ingest_item(item, db_path)

        # Re-ingesting the same items should detect duplicates
        results = [ingest_item(item, db_path) for item in items]
        dup_count = sum(1 for r in results if r.status == "duplicate")
        assert dup_count == 3
