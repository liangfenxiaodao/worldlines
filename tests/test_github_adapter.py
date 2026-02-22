"""Tests for worldlines.ingestion.github_adapter — GitHub Trending adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from worldlines.ingestion.github_adapter import GitHubTrendingAdapter
from worldlines.storage.schema import init_db


def _make_repo(repo_id, name="owner/repo", description="A cool open source project for developers",
               language="Python", stars=1000, pushed_at="2026-02-15T10:00:00Z", topics=None):
    return {
        "id": repo_id,
        "full_name": name,
        "description": description,
        "language": language,
        "stargazers_count": stars,
        "html_url": f"https://github.com/{name}",
        "pushed_at": pushed_at,
        "topics": topics,
    }


def _mock_get(repos, rate_limit_remaining="59"):
    """Build a side_effect for httpx.get that returns repos with rate limit headers."""
    def side_effect(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"items": repos}
        resp.headers = {"X-RateLimit-Remaining": rate_limit_remaining}
        return resp
    return side_effect


class TestGitHubTrendingAdapter:
    def test_fetches_repos(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({"languages": ["python"], "min_stars": 100, "max_items": 10})

        repos = [
            _make_repo(1, "owner/repo1", "A fast Python web framework for building APIs", "Python", 2000),
            _make_repo(2, "owner/repo2", "Machine learning toolkit for data scientists", "Python", 1500),
        ]

        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get(repos)):
            result = adapter.fetch()

        assert len(result) == 2
        assert result[0].title == "owner/repo1"
        assert result[1].title == "owner/repo2"

    def test_deduplicates_seen_ids(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({"languages": ["python"], "min_stars": 100, "max_items": 10})

        repos = [_make_repo(1, "owner/repo1")]

        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get(repos)):
            result1 = adapter.fetch()

        assert len(result1) == 1

        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get(repos)):
            result2 = adapter.fetch()

        assert len(result2) == 0

    def test_state_persistence_across_instances(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        repos = [_make_repo(1, "owner/repo1")]

        adapter1 = GitHubTrendingAdapter(db_path)
        adapter1.configure({"languages": ["python"], "min_stars": 100, "max_items": 10})
        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get(repos)):
            adapter1.fetch()

        adapter2 = GitHubTrendingAdapter(db_path)
        adapter2.configure({"languages": ["python"], "min_stars": 100, "max_items": 10})
        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get(repos)):
            result = adapter2.fetch()

        assert len(result) == 0

    def test_handles_http_error(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({"languages": ["python"], "min_stars": 100, "max_items": 10})

        import httpx as httpx_mod
        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=httpx_mod.ConnectError("fail")):
            result = adapter.fetch()

        assert result == []

    def test_source_fields(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({
            "languages": ["python"], "min_stars": 100,
            "max_items": 10, "source_type": "industry",
        })

        repos = [_make_repo(1, "owner/repo1")]

        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get(repos)):
            result = adapter.fetch()

        assert len(result) == 1
        item = result[0]
        assert item.source_name == "GitHub Trending"
        assert item.source_type == "industry"
        assert item.url == "https://github.com/owner/repo1"

    def test_content_format(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({"languages": ["python"], "min_stars": 100, "max_items": 10})

        repos = [_make_repo(1, "owner/repo1", "A high-performance web framework", "Python", 2000)]

        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get(repos)):
            result = adapter.fetch()

        assert result[0].content == "A high-performance web framework | Python | 2000 stars"

    def test_content_includes_topics(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({"languages": ["python"], "min_stars": 100, "max_items": 10})

        repos = [_make_repo(
            1, "owner/repo1", "A high-performance web framework", "Python", 2000,
            topics=["web", "api", "async"],
        )]

        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get(repos)):
            result = adapter.fetch()

        assert result[0].content == "A high-performance web framework | Python | 2000 stars | Topics: web, api, async"

    def test_content_limits_topics_to_five(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({"languages": ["python"], "min_stars": 100, "max_items": 10})

        repos = [_make_repo(
            1, "owner/repo1", "A comprehensive developer tools suite", "Python", 2000,
            topics=["a", "b", "c", "d", "e", "f", "g"],
        )]

        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get(repos)):
            result = adapter.fetch()

        assert "Topics: a, b, c, d, e" in result[0].content
        assert "f" not in result[0].content

    def test_filters_missing_description(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({"languages": ["python"], "min_stars": 100, "max_items": 10})

        repos = [_make_repo(1, "owner/repo1", None, "Rust", 500)]

        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get(repos)):
            result = adapter.fetch()

        assert len(result) == 0

    def test_filters_short_description(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({"languages": ["python"], "min_stars": 100, "max_items": 10})

        repos = [_make_repo(1, "owner/repo1", "Too short", "Python", 500)]

        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get(repos)):
            result = adapter.fetch()

        assert len(result) == 0

    def test_published_at_from_pushed_at(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({"languages": ["python"], "min_stars": 100, "max_items": 10})

        repos = [_make_repo(1, "owner/repo1", pushed_at="2026-02-15T10:00:00Z")]

        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get(repos)):
            result = adapter.fetch()

        assert result[0].published_at == "2026-02-15T10:00:00Z"

    def test_stops_on_rate_limit_exhaustion(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({
            "languages": ["python", "rust"],
            "min_stars": 100, "max_items": 20,
        })

        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get([], "1")):
            with patch("worldlines.ingestion.github_adapter.time.sleep"):
                result = adapter.fetch()

        assert result == []

    def test_auth_header_with_token(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({"languages": ["python"], "min_stars": 100, "max_items": 10})

        with patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_test123"}):
            with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get([])) as mock_get:
                adapter.fetch()

        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer ghp_test123"

    def test_no_auth_header_without_token(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({"languages": ["python"], "min_stars": 100, "max_items": 10})

        with patch.dict("os.environ", {}, clear=True):
            with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get([])) as mock_get:
                adapter.fetch()

        _, kwargs = mock_get.call_args
        assert "Authorization" not in kwargs["headers"]

    def test_multiple_languages(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({
            "languages": ["python", "rust"],
            "min_stars": 100, "max_items": 20,
        })

        repos = [
            _make_repo(1, "owner/py-repo", "A comprehensive Python data analysis library", "Python", 2000),
            _make_repo(2, "owner/rs-repo", "High-performance Rust systems programming toolkit", "Rust", 1500),
        ]

        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get(repos)):
            with patch("worldlines.ingestion.github_adapter.time.sleep"):
                result = adapter.fetch()

        # Both repos returned from first call, second call sees them as already seen
        assert len(result) == 2

    def test_delay_between_languages(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({
            "languages": ["python", "rust", "go"],
            "min_stars": 100, "max_items": 20,
        })

        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get([])):
            with patch("worldlines.ingestion.github_adapter.time.sleep") as mock_sleep:
                adapter.fetch()

        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(2.0)

    def test_respects_max_items(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        adapter = GitHubTrendingAdapter(db_path)
        adapter.configure({
            "languages": ["python"],
            "min_stars": 100, "max_items": 2,
        })

        repos = [_make_repo(i, f"owner/repo{i}") for i in range(1, 6)]

        with patch("worldlines.ingestion.github_adapter.httpx.get", side_effect=_mock_get(repos)):
            result = adapter.fetch()

        assert len(result) == 2
