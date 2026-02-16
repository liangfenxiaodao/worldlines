"""Tests for worldlines.ingestion.hn_adapter — Hacker News adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from worldlines.ingestion.hn_adapter import HNAdapter
from worldlines.storage.schema import init_db


def _make_hn_item(story_id, title="Test Story", score=150, item_type="story", url=None, time_val=1700000000):
    return {
        "id": story_id,
        "type": item_type,
        "title": title,
        "score": score,
        "url": url or f"https://example.com/{story_id}",
        "time": time_val,
    }


def _mock_get(top_ids, items_by_id):
    """Build a side_effect for httpx.get that returns top stories and individual items."""
    def side_effect(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "topstories" in url:
            resp.json.return_value = top_ids
        else:
            # Extract item ID from URL
            item_id = int(url.rstrip(".json").split("/")[-1])
            resp.json.return_value = items_by_id.get(item_id)
        return resp
    return side_effect


class TestHNAdapter:
    def test_fetches_stories_above_score_threshold(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = HNAdapter(db_path)
        adapter.configure({"min_score": 100, "max_items": 10})

        items_by_id = {
            1: _make_hn_item(1, "High Score", score=200),
            2: _make_hn_item(2, "Low Score", score=50),
            3: _make_hn_item(3, "Medium Score", score=100),
        }

        with patch("worldlines.ingestion.hn_adapter.httpx.get", side_effect=_mock_get([1, 2, 3], items_by_id)):
            with patch("worldlines.ingestion.hn_adapter.time.sleep"):
                result = adapter.fetch()

        assert len(result) == 2
        titles = {item.title for item in result}
        assert "High Score" in titles
        assert "Medium Score" in titles
        assert "Low Score" not in titles

    def test_skips_non_story_types(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = HNAdapter(db_path)
        adapter.configure({"min_score": 0, "max_items": 10})

        items_by_id = {
            1: _make_hn_item(1, "A Story", score=200, item_type="story"),
            2: {**_make_hn_item(2, "A Comment", score=200), "type": "comment"},
        }

        with patch("worldlines.ingestion.hn_adapter.httpx.get", side_effect=_mock_get([1, 2], items_by_id)):
            with patch("worldlines.ingestion.hn_adapter.time.sleep"):
                result = adapter.fetch()

        assert len(result) == 1
        assert result[0].title == "A Story"

    def test_deduplicates_seen_ids(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = HNAdapter(db_path)
        adapter.configure({"min_score": 0, "max_items": 10})

        items_by_id = {
            1: _make_hn_item(1, "Story One", score=200),
            2: _make_hn_item(2, "Story Two", score=200),
        }

        with patch("worldlines.ingestion.hn_adapter.httpx.get", side_effect=_mock_get([1, 2], items_by_id)):
            with patch("worldlines.ingestion.hn_adapter.time.sleep"):
                result1 = adapter.fetch()

        assert len(result1) == 2

        # Second fetch — same IDs should be skipped
        with patch("worldlines.ingestion.hn_adapter.httpx.get", side_effect=_mock_get([1, 2], items_by_id)):
            with patch("worldlines.ingestion.hn_adapter.time.sleep"):
                result2 = adapter.fetch()

        assert len(result2) == 0

    def test_respects_max_items(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = HNAdapter(db_path)
        adapter.configure({"min_score": 0, "max_items": 2})

        items_by_id = {
            i: _make_hn_item(i, f"Story {i}", score=200)
            for i in range(1, 6)
        }

        with patch("worldlines.ingestion.hn_adapter.httpx.get", side_effect=_mock_get([1, 2, 3, 4, 5], items_by_id)):
            with patch("worldlines.ingestion.hn_adapter.time.sleep"):
                result = adapter.fetch()

        assert len(result) == 2

    def test_handles_top_stories_http_error(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = HNAdapter(db_path)
        adapter.configure({})

        import httpx as httpx_mod
        with patch("worldlines.ingestion.hn_adapter.httpx.get", side_effect=httpx_mod.ConnectError("fail")):
            result = adapter.fetch()

        assert result == []

    def test_handles_individual_item_fetch_failure(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = HNAdapter(db_path)
        adapter.configure({"min_score": 0, "max_items": 10})

        import httpx as httpx_mod

        call_count = 0

        def side_effect(url, **kwargs):
            nonlocal call_count
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "topstories" in url:
                resp.json.return_value = [1, 2]
                return resp
            call_count += 1
            if call_count == 1:
                raise httpx_mod.ConnectError("fail")
            resp.json.return_value = _make_hn_item(2, "Story Two", score=200)
            return resp

        with patch("worldlines.ingestion.hn_adapter.httpx.get", side_effect=side_effect):
            with patch("worldlines.ingestion.hn_adapter.time.sleep"):
                result = adapter.fetch()

        assert len(result) == 1
        assert result[0].title == "Story Two"

    def test_state_persistence(self, tmp_path):
        """Verify seen IDs survive across adapter instances."""
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        items_by_id = {1: _make_hn_item(1, "Persistent", score=200)}

        adapter1 = HNAdapter(db_path)
        adapter1.configure({"min_score": 0, "max_items": 10})
        with patch("worldlines.ingestion.hn_adapter.httpx.get", side_effect=_mock_get([1], items_by_id)):
            with patch("worldlines.ingestion.hn_adapter.time.sleep"):
                adapter1.fetch()

        # New adapter instance should see the same state
        adapter2 = HNAdapter(db_path)
        adapter2.configure({"min_score": 0, "max_items": 10})
        with patch("worldlines.ingestion.hn_adapter.httpx.get", side_effect=_mock_get([1], items_by_id)):
            with patch("worldlines.ingestion.hn_adapter.time.sleep"):
                result = adapter2.fetch()

        assert len(result) == 0

    def test_source_fields(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = HNAdapter(db_path)
        adapter.configure({"min_score": 0, "max_items": 10})

        items_by_id = {1: _make_hn_item(1, "Test", score=200)}

        with patch("worldlines.ingestion.hn_adapter.httpx.get", side_effect=_mock_get([1], items_by_id)):
            with patch("worldlines.ingestion.hn_adapter.time.sleep"):
                result = adapter.fetch()

        assert len(result) == 1
        item = result[0]
        assert item.source_name == "Hacker News"
        assert item.source_type == "news"
        assert item.published_at is not None
