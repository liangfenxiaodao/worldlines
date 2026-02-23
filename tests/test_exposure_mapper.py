"""Tests for worldlines.exposure.mapper — exposure mapping pipeline."""

from __future__ import annotations

import json
from unittest.mock import patch

from worldlines.exposure.mapper import ExposureResult, map_exposures
from worldlines.storage.connection import get_connection
from worldlines.storage.schema import init_db


def _make_analysis(**overrides):
    defaults = {
        "analysis_id": "a-1",
        "dimensions": json.dumps([
            {"dimension": "compute_and_computational_paradigms", "relevance": "primary"}
        ]),
        "change_type": "reinforcing",
        "time_horizon": "medium_term",
        "summary": "NVIDIA announces next-gen GPU architecture.",
        "importance": "high",
        "key_entities": json.dumps(["NVIDIA", "TSMC"]),
    }
    defaults.update(overrides)
    return defaults


def _make_item(**overrides):
    defaults = {
        "title": "NVIDIA unveils Blackwell GPU",
        "source_name": "Reuters",
        "source_type": "news",
    }
    defaults.update(overrides)
    return defaults


_VALID_LLM_RESPONSE = json.dumps({
    "exposures": [
        {
            "ticker": "NVDA",
            "exposure_type": "direct",
            "business_role": "infrastructure_operator",
            "exposure_strength": "core",
            "confidence": "high",
            "dimensions_implicated": ["compute_and_computational_paradigms"],
            "rationale": "NVIDIA designs and sells the GPU accelerators referenced.",
        },
        {
            "ticker": "TSM",
            "exposure_type": "indirect",
            "business_role": "upstream_supplier",
            "exposure_strength": "material",
            "confidence": "high",
            "dimensions_implicated": ["compute_and_computational_paradigms"],
            "rationale": "TSMC manufactures NVIDIA chips on advanced nodes.",
        },
    ],
    "skipped_reason": None,
})

_SKIPPED_LLM_RESPONSE = json.dumps({
    "exposures": [],
    "skipped_reason": "Analysis discusses abstract governance concepts without identifiable company exposure.",
})


class TestMapExposuresSuccess:
    @patch("worldlines.exposure.mapper._call_llm", return_value=_VALID_LLM_RESPONSE)
    def test_success_returns_exposure_record(self, mock_llm, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Seed item and analysis for FK constraints
        with get_connection(db_path) as conn:
            conn.execute(
                "INSERT INTO items (id, title, source_name, source_type, timestamp, "
                "content, canonical_link, ingested_at, dedup_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("item-1", "Test", "Src", "news", "2025-01-01T00:00:00Z",
                 "content", "https://x.com", "2025-01-01T00:00:00Z", "hash-1"),
            )
            conn.execute(
                "INSERT INTO analyses (id, item_id, dimensions, change_type, time_horizon, "
                "summary, importance, key_entities, analyzed_at, analysis_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("a-1", "item-1",
                 json.dumps([{"dimension": "compute_and_computational_paradigms", "relevance": "primary"}]),
                 "reinforcing", "medium_term", "Summary", "high",
                 json.dumps(["NVIDIA"]), "2025-01-01T00:00:00Z", "v1"),
            )

        result = map_exposures(
            _make_analysis(),
            _make_item(),
            api_key="test-key",
            model="test-model",
            exposure_mapping_version="v1",
            database_path=db_path,
        )

        assert isinstance(result, ExposureResult)
        assert result.error is None
        assert result.exposure_record is not None
        assert len(result.exposure_record["exposures"]) == 2
        assert result.exposure_record["exposures"][0]["ticker"] == "NVDA"
        assert result.exposure_record["analysis_id"] == "a-1"

    @patch("worldlines.exposure.mapper._call_llm", return_value=_VALID_LLM_RESPONSE)
    def test_persists_to_database(self, mock_llm, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        with get_connection(db_path) as conn:
            conn.execute(
                "INSERT INTO items (id, title, source_name, source_type, timestamp, "
                "content, canonical_link, ingested_at, dedup_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("item-1", "Test", "Src", "news", "2025-01-01T00:00:00Z",
                 "content", "https://x.com", "2025-01-01T00:00:00Z", "hash-1"),
            )
            conn.execute(
                "INSERT INTO analyses (id, item_id, dimensions, change_type, time_horizon, "
                "summary, importance, key_entities, analyzed_at, analysis_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("a-1", "item-1",
                 json.dumps([{"dimension": "compute_and_computational_paradigms", "relevance": "primary"}]),
                 "reinforcing", "medium_term", "Summary", "high",
                 json.dumps(["NVIDIA"]), "2025-01-01T00:00:00Z", "v1"),
            )

        map_exposures(
            _make_analysis(),
            _make_item(),
            api_key="test-key",
            model="test-model",
            exposure_mapping_version="v1",
            database_path=db_path,
        )

        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM exposures WHERE analysis_id = 'a-1'"
            ).fetchone()
        assert row is not None
        exposures = json.loads(row["exposures"])
        assert len(exposures) == 2
        assert row["skipped_reason"] is None


class TestMapExposuresSkipped:
    @patch("worldlines.exposure.mapper._call_llm", return_value=_SKIPPED_LLM_RESPONSE)
    def test_skipped_returns_reason(self, mock_llm, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        with get_connection(db_path) as conn:
            conn.execute(
                "INSERT INTO items (id, title, source_name, source_type, timestamp, "
                "content, canonical_link, ingested_at, dedup_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("item-1", "Test", "Src", "news", "2025-01-01T00:00:00Z",
                 "content", "https://x.com", "2025-01-01T00:00:00Z", "hash-1"),
            )
            conn.execute(
                "INSERT INTO analyses (id, item_id, dimensions, change_type, time_horizon, "
                "summary, importance, key_entities, analyzed_at, analysis_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("a-1", "item-1",
                 json.dumps([{"dimension": "compute_and_computational_paradigms", "relevance": "primary"}]),
                 "reinforcing", "medium_term", "Summary", "high",
                 json.dumps(["NVIDIA"]), "2025-01-01T00:00:00Z", "v1"),
            )

        result = map_exposures(
            _make_analysis(),
            _make_item(),
            api_key="test-key",
            model="test-model",
            exposure_mapping_version="v1",
            database_path=db_path,
        )

        assert result.error is None
        assert result.skipped_reason is not None
        assert "governance" in result.skipped_reason.lower()
        assert result.exposure_record is not None
        assert len(result.exposure_record["exposures"]) == 0


class TestMapExposuresErrors:
    @patch("worldlines.exposure.mapper._call_llm", side_effect=Exception("API timeout"))
    def test_api_error(self, mock_llm, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        result = map_exposures(
            _make_analysis(),
            _make_item(),
            api_key="test-key",
            model="test-model",
            exposure_mapping_version="v1",
            database_path=db_path,
        )

        assert result.error is not None
        assert result.error["code"] == "api_error"
        assert result.exposure_record is None

    @patch("worldlines.exposure.mapper._call_llm", return_value="not json at all")
    def test_parse_error(self, mock_llm, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        result = map_exposures(
            _make_analysis(),
            _make_item(),
            api_key="test-key",
            model="test-model",
            exposure_mapping_version="v1",
            database_path=db_path,
        )

        assert result.error is not None
        assert result.error["code"] == "parse_error"
        assert result.exposure_record is None

    @patch("worldlines.exposure.mapper._call_llm")
    def test_validation_failure(self, mock_llm, tmp_path):
        # Return JSON that fails validation (invalid exposure_type)
        mock_llm.return_value = json.dumps({
            "exposures": [{
                "ticker": "NVDA",
                "exposure_type": "tangential",
                "business_role": "infrastructure_operator",
                "exposure_strength": "core",
                "confidence": "high",
                "dimensions_implicated": ["compute_and_computational_paradigms"],
                "rationale": "Test rationale.",
            }],
            "skipped_reason": None,
        })

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        result = map_exposures(
            _make_analysis(),
            _make_item(),
            api_key="test-key",
            model="test-model",
            exposure_mapping_version="v1",
            database_path=db_path,
        )

        assert result.error is not None
        assert result.error["code"] == "mapping_uncertain"
        assert result.exposure_record is None
