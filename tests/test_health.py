"""Tests for the /health endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from worldlines.storage.schema import init_db
from worldlines.web.app import create_app
from worldlines.web.config import WebConfig


class TestHealthEndpoint:
    def test_healthy_response(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        config = WebConfig(database_path=db_path)
        app = create_app(config)
        client = TestClient(app)

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"] == "ok"

    def test_unhealthy_when_db_missing(self, tmp_path):
        db_path = str(tmp_path / "nonexistent" / "missing.db")
        config = WebConfig(database_path=db_path)
        app = create_app(config)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/health")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "error"
        assert "detail" in data

    def test_health_not_under_api_prefix(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        config = WebConfig(database_path=db_path)
        app = create_app(config)
        client = TestClient(app)

        # /health should work at root
        assert client.get("/health").status_code == 200
        # /api/v1/health should NOT exist
        resp = client.get("/api/v1/health")
        assert resp.status_code != 200
