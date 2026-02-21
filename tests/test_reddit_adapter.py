"""Tests for worldlines.ingestion.reddit_adapter — Reddit adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from worldlines.ingestion.reddit_adapter import RedditAdapter
from worldlines.storage.schema import init_db


def _make_post(post_id, title="Test Post", score=150, subreddit="technology",
               selftext="", created_utc=1700000000, url=None):
    return {
        "data": {
            "id": post_id,
            "title": title,
            "score": score,
            "subreddit": subreddit,
            "selftext": selftext,
            "url": url or f"https://example.com/{post_id}",
            "permalink": f"/r/{subreddit}/comments/{post_id}/",
            "created_utc": created_utc,
        }
    }


def _make_response(posts):
    return {"data": {"children": posts}}


def _mock_get(responses_by_subreddit):
    """Build a side_effect for httpx.get that routes by subreddit in URL."""
    def side_effect(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        for sub_name, response_data in responses_by_subreddit.items():
            if f"/r/{sub_name}/" in url:
                resp.json.return_value = response_data
                return resp
        resp.json.return_value = _make_response([])
        return resp
    return side_effect


class TestRedditAdapter:
    def test_fetches_posts_above_score_threshold(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = RedditAdapter(db_path)
        adapter.configure({
            "subreddits": [{"name": "technology", "source_type": "news", "min_score": 100}]
        })

        posts = [
            _make_post("a1", "High Score", score=200),
            _make_post("a2", "Low Score", score=50),
            _make_post("a3", "At Threshold", score=100),
        ]
        responses = {"technology": _make_response(posts)}

        with patch("worldlines.ingestion.reddit_adapter.httpx.get", side_effect=_mock_get(responses)):
            result = adapter.fetch()

        assert len(result) == 2
        titles = {item.title for item in result}
        assert "High Score" in titles
        assert "At Threshold" in titles
        assert "Low Score" not in titles

    def test_deduplicates_seen_ids(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = RedditAdapter(db_path)
        adapter.configure({
            "subreddits": [{"name": "technology", "source_type": "news", "min_score": 0}]
        })

        posts = [_make_post("a1", "Post One", score=200)]
        responses = {"technology": _make_response(posts)}

        with patch("worldlines.ingestion.reddit_adapter.httpx.get", side_effect=_mock_get(responses)):
            result1 = adapter.fetch()

        assert len(result1) == 1

        with patch("worldlines.ingestion.reddit_adapter.httpx.get", side_effect=_mock_get(responses)):
            result2 = adapter.fetch()

        assert len(result2) == 0

    def test_state_persistence_across_instances(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        posts = [_make_post("a1", "Persistent", score=200)]
        responses = {"technology": _make_response(posts)}

        adapter1 = RedditAdapter(db_path)
        adapter1.configure({
            "subreddits": [{"name": "technology", "source_type": "news", "min_score": 0}]
        })
        with patch("worldlines.ingestion.reddit_adapter.httpx.get", side_effect=_mock_get(responses)):
            adapter1.fetch()

        adapter2 = RedditAdapter(db_path)
        adapter2.configure({
            "subreddits": [{"name": "technology", "source_type": "news", "min_score": 0}]
        })
        with patch("worldlines.ingestion.reddit_adapter.httpx.get", side_effect=_mock_get(responses)):
            result = adapter2.fetch()

        assert len(result) == 0

    def test_handles_http_error(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = RedditAdapter(db_path)
        adapter.configure({
            "subreddits": [{"name": "technology", "source_type": "news", "min_score": 0}]
        })

        import httpx as httpx_mod
        with patch("worldlines.ingestion.reddit_adapter.httpx.get", side_effect=httpx_mod.ConnectError("fail")):
            result = adapter.fetch()

        assert result == []

    def test_source_fields(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = RedditAdapter(db_path)
        adapter.configure({
            "subreddits": [{"name": "MachineLearning", "source_type": "research", "min_score": 0}]
        })

        posts = [_make_post("a1", "ML Post", score=200, subreddit="MachineLearning")]
        responses = {"MachineLearning": _make_response(posts)}

        with patch("worldlines.ingestion.reddit_adapter.httpx.get", side_effect=_mock_get(responses)):
            result = adapter.fetch()

        assert len(result) == 1
        item = result[0]
        assert item.source_name == "Reddit r/MachineLearning"
        assert item.source_type == "research"
        assert item.published_at is not None

    def test_content_includes_selftext(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = RedditAdapter(db_path)
        adapter.configure({
            "subreddits": [{"name": "technology", "source_type": "news", "min_score": 0}]
        })

        posts = [_make_post("a1", "Title Here", score=200, selftext="Body text here")]
        responses = {"technology": _make_response(posts)}

        with patch("worldlines.ingestion.reddit_adapter.httpx.get", side_effect=_mock_get(responses)):
            result = adapter.fetch()

        assert len(result) == 1
        assert result[0].content == "Title Here\n\nBody text here"

    def test_content_is_title_when_no_selftext(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = RedditAdapter(db_path)
        adapter.configure({
            "subreddits": [{"name": "technology", "source_type": "news", "min_score": 0}]
        })

        posts = [_make_post("a1", "Link Post", score=200, selftext="")]
        responses = {"technology": _make_response(posts)}

        with patch("worldlines.ingestion.reddit_adapter.httpx.get", side_effect=_mock_get(responses)):
            result = adapter.fetch()

        assert len(result) == 1
        assert result[0].content == "Link Post"

    def test_multiple_subreddits(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = RedditAdapter(db_path)
        adapter.configure({
            "subreddits": [
                {"name": "technology", "source_type": "news", "min_score": 0},
                {"name": "energy", "source_type": "industry", "min_score": 0},
            ]
        })

        responses = {
            "technology": _make_response([_make_post("a1", "Tech Post", score=200)]),
            "energy": _make_response([_make_post("b1", "Energy Post", score=200, subreddit="energy")]),
        }

        with patch("worldlines.ingestion.reddit_adapter.httpx.get", side_effect=_mock_get(responses)):
            with patch("worldlines.ingestion.reddit_adapter.time.sleep"):
                result = adapter.fetch()

        assert len(result) == 2
        source_names = {item.source_name for item in result}
        assert "Reddit r/technology" in source_names
        assert "Reddit r/energy" in source_names

    def test_delay_between_subreddits(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = RedditAdapter(db_path)
        adapter.configure({
            "subreddits": [
                {"name": "technology", "source_type": "news", "min_score": 0},
                {"name": "energy", "source_type": "industry", "min_score": 0},
            ]
        })

        responses = {
            "technology": _make_response([]),
            "energy": _make_response([]),
        }

        with patch("worldlines.ingestion.reddit_adapter.httpx.get", side_effect=_mock_get(responses)):
            with patch("worldlines.ingestion.reddit_adapter.time.sleep") as mock_sleep:
                adapter.fetch()

        mock_sleep.assert_called_once_with(0.5)

    def test_skips_empty_title(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = RedditAdapter(db_path)
        adapter.configure({
            "subreddits": [{"name": "technology", "source_type": "news", "min_score": 0}]
        })

        posts = [
            _make_post("a1", "", score=200),
            _make_post("a2", "Valid Title", score=200),
        ]
        responses = {"technology": _make_response(posts)}

        with patch("worldlines.ingestion.reddit_adapter.httpx.get", side_effect=_mock_get(responses)):
            result = adapter.fetch()

        assert len(result) == 1
        assert result[0].title == "Valid Title"
