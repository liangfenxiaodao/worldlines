"""Tests for worldlines.linking.rationale — generate_link_rationale()."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from worldlines.linking.rationale import RationaleResult, generate_link_rationale

_SOURCE = {
    "title": "TSMC expands Arizona fab",
    "summary": "TSMC is expanding its Arizona semiconductor fab capacity.",
    "dimensions": json.dumps([{"dimension": "compute_and_computational_paradigms", "relevance": "primary"}]),
    "change_type": "reinforcing",
    "timestamp": "2025-06-15T08:00:00+00:00",
}

_TARGET = {
    "title": "US chip shortage continues",
    "summary": "US semiconductor supply remains constrained.",
    "dimensions": json.dumps([{"dimension": "energy_resources_physical_constraints", "relevance": "primary"}]),
    "change_type": "friction",
    "timestamp": "2025-05-01T08:00:00+00:00",
}

_SHARED_TICKERS = ["TSM"]
_LINK_TYPE = "contradicts"
_CALL_KWARGS = dict(
    api_key="test-key",
    model="test-model",
    rationale_version="v1",
    temperature=0.0,
    max_retries=1,
    timeout=10,
)


class TestGenerateLinkRationale:
    def test_returns_rationale_on_success(self):
        response = json.dumps(
            {"rationale": "Both signals relate to semiconductor supply constraints affecting TSMC."}
        )
        with patch(
            "worldlines.linking.rationale._call_llm", return_value=response
        ) as mock_llm:
            result = generate_link_rationale(
                _SOURCE, _TARGET, _SHARED_TICKERS, _LINK_TYPE, **_CALL_KWARGS
            )

        assert result.rationale == (
            "Both signals relate to semiconductor supply constraints affecting TSMC."
        )
        assert result.error is None
        mock_llm.assert_called_once()

    def test_returns_error_on_api_exception(self):
        with patch(
            "worldlines.linking.rationale._call_llm",
            side_effect=Exception("network timeout"),
        ):
            result = generate_link_rationale(
                _SOURCE, _TARGET, _SHARED_TICKERS, _LINK_TYPE, **_CALL_KWARGS
            )

        assert result.rationale is None
        assert result.error is not None
        assert result.error["code"] == "api_error"
        assert "network timeout" in result.error["message"]

    def test_returns_error_on_parse_failure(self):
        with patch(
            "worldlines.linking.rationale._call_llm",
            return_value="not valid json {{{{",
        ):
            result = generate_link_rationale(
                _SOURCE, _TARGET, _SHARED_TICKERS, _LINK_TYPE, **_CALL_KWARGS
            )

        assert result.rationale is None
        assert result.error is not None
        assert result.error["code"] == "parse_error"

    def test_returns_error_on_missing_rationale_key(self):
        with patch(
            "worldlines.linking.rationale._call_llm",
            return_value=json.dumps({}),
        ):
            result = generate_link_rationale(
                _SOURCE, _TARGET, _SHARED_TICKERS, _LINK_TYPE, **_CALL_KWARGS
            )

        assert result.rationale is None
        assert result.error is not None
        assert result.error["code"] == "missing_rationale"

    def test_returns_error_on_empty_rationale(self):
        with patch(
            "worldlines.linking.rationale._call_llm",
            return_value=json.dumps({"rationale": ""}),
        ):
            result = generate_link_rationale(
                _SOURCE, _TARGET, _SHARED_TICKERS, _LINK_TYPE, **_CALL_KWARGS
            )

        assert result.rationale is None
        assert result.error is not None
        assert result.error["code"] == "missing_rationale"

    def test_result_is_frozen_dataclass(self):
        response = json.dumps({"rationale": "Some rationale text."})
        with patch("worldlines.linking.rationale._call_llm", return_value=response):
            result = generate_link_rationale(
                _SOURCE, _TARGET, _SHARED_TICKERS, _LINK_TYPE, **_CALL_KWARGS
            )

        assert isinstance(result, RationaleResult)
        with pytest.raises(Exception):
            result.rationale = "mutated"  # type: ignore[misc]
