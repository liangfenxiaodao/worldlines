"""Integration tests for the Worldlines web API endpoints."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from worldlines.storage.connection import get_connection
from worldlines.storage.schema import init_db
from worldlines.web.app import create_app
from worldlines.web.config import WebConfig


# --- Seed helpers ---


def _seed_item(conn, item_id, **overrides):
    """Insert a test item into the items table."""
    defaults = {
        "title": f"Title {item_id}",
        "source_name": "Test Source",
        "source_type": "news",
        "timestamp": "2025-06-15T08:00:00+00:00",
        "content": f"Content for {item_id}.",
        "canonical_link": f"https://example.com/{item_id}",
        "ingested_at": "2025-06-15T08:01:00+00:00",
        "dedup_hash": f"hash-{item_id}",
    }
    defaults.update(overrides)
    conn.execute(
        "INSERT INTO items "
        "(id, title, source_name, source_type, timestamp, content, "
        "canonical_link, ingested_at, dedup_hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            item_id,
            defaults["title"],
            defaults["source_name"],
            defaults["source_type"],
            defaults["timestamp"],
            defaults["content"],
            defaults["canonical_link"],
            defaults["ingested_at"],
            defaults["dedup_hash"],
        ),
    )


def _seed_analysis(conn, analysis_id, item_id, **overrides):
    """Insert a test analysis into the analyses table."""
    defaults = {
        "dimensions": [{"dimension": "compute_and_computational_paradigms", "relevance": "primary"}],
        "change_type": "reinforcing",
        "time_horizon": "medium_term",
        "summary": f"Summary for {item_id}.",
        "importance": "medium",
        "key_entities": ["TestEntity"],
        "analyzed_at": "2025-06-15T10:00:00+00:00",
        "analysis_version": "v1",
    }
    defaults.update(overrides)
    conn.execute(
        "INSERT INTO analyses "
        "(id, item_id, dimensions, change_type, time_horizon, summary, "
        "importance, key_entities, analyzed_at, analysis_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            analysis_id,
            item_id,
            json.dumps(defaults["dimensions"]),
            defaults["change_type"],
            defaults["time_horizon"],
            defaults["summary"],
            defaults["importance"],
            json.dumps(defaults["key_entities"]),
            defaults["analyzed_at"],
            defaults["analysis_version"],
        ),
    )


def _seed_digest(conn, digest_id, digest_date, **overrides):
    """Insert a test digest into the digests table."""
    defaults = {
        "item_count": 3,
        "dimension_breakdown": {"compute_and_computational_paradigms": 2},
        "change_type_distribution": {"reinforcing": 2, "friction": 1},
        "high_importance_items": [{"item_id": "item-1", "analysis_id": "a-1"}],
        "summary_en": None,
        "summary_zh": None,
        "message_text": "<b>Test digest</b>",
        "sent_at": f"{digest_date}T18:00:00+00:00",
        "telegram_message_ids": [100],
    }
    defaults.update(overrides)
    conn.execute(
        "INSERT INTO digests "
        "(id, digest_date, item_count, dimension_breakdown, "
        "change_type_distribution, high_importance_items, "
        "summary_en, summary_zh, "
        "message_text, sent_at, telegram_message_ids) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            digest_id,
            digest_date,
            defaults["item_count"],
            json.dumps(defaults["dimension_breakdown"]),
            json.dumps(defaults["change_type_distribution"]),
            json.dumps(defaults["high_importance_items"]),
            defaults["summary_en"],
            defaults["summary_zh"],
            defaults["message_text"],
            defaults["sent_at"],
            json.dumps(defaults["telegram_message_ids"]),
        ),
    )


# --- Fixtures ---


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture()
def seeded_db(db_path):
    """Database with 5 items, 5 analyses, and 2 digests."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        # Item 1 — news, high importance, reinforcing, compute
        _seed_item(conn, "item-1", source_type="news", timestamp="2025-06-15T08:00:00+00:00")
        _seed_analysis(
            conn, "a-1", "item-1",
            importance="high",
            change_type="reinforcing",
            dimensions=[{"dimension": "compute_and_computational_paradigms", "relevance": "primary"}],
            analyzed_at="2025-06-15T10:00:00+00:00",
        )

        # Item 2 — policy, medium importance, friction, governance
        _seed_item(conn, "item-2", source_type="policy", timestamp="2025-06-14T12:00:00+00:00")
        _seed_analysis(
            conn, "a-2", "item-2",
            importance="medium",
            change_type="friction",
            dimensions=[{"dimension": "governance_regulation_and_societal_response", "relevance": "primary"}],
            analyzed_at="2025-06-14T12:00:00+00:00",
        )

        # Item 3 — report, low importance, neutral, energy
        _seed_item(conn, "item-3", source_type="report", timestamp="2025-06-13T09:00:00+00:00")
        _seed_analysis(
            conn, "a-3", "item-3",
            importance="low",
            change_type="neutral",
            dimensions=[{"dimension": "energy_resources_and_physical_constraints", "relevance": "primary"}],
            analyzed_at="2025-06-13T09:00:00+00:00",
        )

        # Item 4 — research, high importance, early_signal, capital + tech adoption
        _seed_item(conn, "item-4", source_type="research", timestamp="2025-06-12T07:00:00+00:00")
        _seed_analysis(
            conn, "a-4", "item-4",
            importance="high",
            change_type="early_signal",
            dimensions=[
                {"dimension": "capital_flows_and_business_models", "relevance": "primary"},
                {"dimension": "technology_adoption_and_industrial_diffusion", "relevance": "secondary"},
            ],
            analyzed_at="2025-06-12T07:00:00+00:00",
        )

        # Item 5 — industry, medium importance, reinforcing, tech adoption
        _seed_item(conn, "item-5", source_type="industry", timestamp="2025-06-16T10:00:00+00:00")
        _seed_analysis(
            conn, "a-5", "item-5",
            importance="medium",
            change_type="reinforcing",
            dimensions=[{"dimension": "technology_adoption_and_industrial_diffusion", "relevance": "primary"}],
            analyzed_at="2025-06-16T10:00:00+00:00",
        )

        # Digests
        _seed_digest(
            conn, "digest-1", "2025-06-15",
            summary_en="English summary of the digest.",
            summary_zh="Digest的中文摘要。",
        )
        _seed_digest(conn, "digest-2", "2025-06-14", item_count=2)

    return db_path


@pytest.fixture()
def client(seeded_db):
    config = WebConfig(database_path=seeded_db)
    app = create_app(config)
    return TestClient(app)


# --- Tests: Stats ---


class TestStats:
    def test_stats_returns_all_fields(self, client):
        resp = client.get("/api/v1/stats")
        assert resp.status_code == 200
        data = resp.json()
        expected_keys = {
            "total_items",
            "total_analyses",
            "total_digests",
            "latest_digest_date",
            "dimension_breakdown",
            "change_type_distribution",
            "importance_distribution",
        }
        assert expected_keys == set(data.keys())

    def test_stats_counts_match_seeded_data(self, client):
        data = client.get("/api/v1/stats").json()
        assert data["total_items"] == 5
        assert data["total_analyses"] == 5
        assert data["total_digests"] == 2


# --- Tests: Digests ---


class TestDigests:
    def test_list_digests_returns_paginated(self, client):
        resp = client.get("/api/v1/digests")
        assert resp.status_code == 200
        data = resp.json()
        for key in ("total", "page", "per_page", "pages"):
            assert key in data
        assert data["total"] == 2
        assert data["page"] == 1

    def test_list_digests_ordered_by_date_desc(self, client):
        data = client.get("/api/v1/digests").json()
        dates = [d["digest_date"] for d in data["digests"]]
        assert dates[0] > dates[1]

    def test_get_digest_by_date_found(self, client):
        resp = client.get("/api/v1/digests/2025-06-15")
        assert resp.status_code == 200
        data = resp.json()
        assert data["digest_date"] == "2025-06-15"
        assert "high_importance_items" in data
        assert "message_text" in data

    def test_get_digest_includes_summaries(self, client):
        resp = client.get("/api/v1/digests/2025-06-15")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary_en"] == "English summary of the digest."
        assert data["summary_zh"] == "Digest的中文摘要。"

    def test_get_digest_null_summaries(self, client):
        resp = client.get("/api/v1/digests/2025-06-14")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary_en"] is None
        assert data["summary_zh"] is None

    def test_get_digest_by_date_not_found(self, client):
        resp = client.get("/api/v1/digests/1999-01-01")
        assert resp.status_code == 404


# --- Tests: Items ---


class TestItems:
    def test_list_items_returns_paginated(self, client):
        resp = client.get("/api/v1/items")
        assert resp.status_code == 200
        data = resp.json()
        for key in ("items", "total", "page", "per_page", "pages"):
            assert key in data
        assert data["total"] == 5
        assert data["page"] == 1

    def test_list_items_filter_by_change_type(self, client):
        data = client.get("/api/v1/items?change_type=friction").json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["change_type"] == "friction"

    def test_list_items_filter_by_dimension(self, client):
        dim = "technology_adoption_and_industrial_diffusion"
        data = client.get(f"/api/v1/items?dimension={dim}").json()
        assert data["total"] >= 1
        for item in data["items"]:
            dims = [d["dimension"] for d in item["dimensions"]]
            assert dim in dims

    def test_list_items_filter_by_importance(self, client):
        data = client.get("/api/v1/items?importance=high").json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["importance"] == "high"

    def test_list_items_filter_by_date_range(self, client):
        data = client.get(
            "/api/v1/items?date_from=2025-06-14T00:00:00&date_to=2025-06-15T00:00:00"
        ).json()
        # Only item-2 has analyzed_at in [2025-06-14, 2025-06-15)
        assert data["total"] == 1
        assert data["items"][0]["id"] == "item-2"

    def test_list_items_sort_order(self, client):
        data = client.get("/api/v1/items?sort=timestamp&order=asc").json()
        timestamps = [item["timestamp"] for item in data["items"]]
        assert timestamps == sorted(timestamps)

    def test_get_item_by_id_found(self, client):
        resp = client.get("/api/v1/items/item-1")
        assert resp.status_code == 200
        data = resp.json()
        assert "item" in data
        assert "analysis" in data
        assert data["item"]["id"] == "item-1"

    def test_get_item_by_id_not_found(self, client):
        resp = client.get("/api/v1/items/nonexistent")
        assert resp.status_code == 404


# --- Tests: Edge Cases ---


class TestEdgeCases:
    def test_per_page_capped_at_100(self, client):
        resp = client.get("/api/v1/items?per_page=500")
        assert resp.status_code == 422

    def test_page_beyond_range_returns_empty(self, client):
        data = client.get("/api/v1/items?page=999").json()
        assert data["items"] == []
        assert data["total"] == 5
