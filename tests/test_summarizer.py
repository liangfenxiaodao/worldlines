"""Tests for worldlines.digest.summarizer — bilingual digest summary generation."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from worldlines.digest.digest import DigestItem
from worldlines.digest.summarizer import (
    SummaryResult,
    format_summary_prompt,
    generate_digest_summary,
    validate_summary,
    _parse_json,
)


VALID_SUMMARY_RESPONSE = json.dumps({
    "summary_en": "Structural shifts in compute capacity and energy constraints dominate.",
    "summary_zh": "\u8ba1\u7b97\u80fd\u529b\u548c\u80fd\u6e90\u7ea6\u675f\u7684\u7ed3\u6784\u6027\u53d8\u5316\u5360\u636e\u4e3b\u5bfc\u5730\u4f4d\u3002",
})


def _make_item(**overrides) -> DigestItem:
    """Create a test DigestItem."""
    defaults = {
        "item_id": "item-001",
        "analysis_id": "analysis-001",
        "title": "TSMC Expands 2nm Capacity",
        "summary": "TSMC expands advanced node capacity for AI accelerators.",
        "dimensions": ["compute_and_computational_paradigms"],
        "change_type": "reinforcing",
        "time_horizon": "medium_term",
        "importance": "high",
        "canonical_link": "https://example.com/article",
    }
    defaults.update(overrides)
    return DigestItem(**defaults)


def _mock_call_llm(**kwargs):
    """Mock _call_llm returning a valid summary JSON response."""
    return VALID_SUMMARY_RESPONSE


# --- Empty items ---


class TestEmptyItems:
    def test_returns_none_summaries(self):
        result = generate_digest_summary(
            [],
            api_key="test-key",
            model="test-model",
        )
        assert result.summary_en is None
        assert result.summary_zh is None
        assert result.error is None


# --- Successful generation ---


class TestSuccessfulGeneration:
    @patch("worldlines.digest.summarizer._call_llm", side_effect=_mock_call_llm)
    def test_returns_both_summaries(self, mock_llm):
        result = generate_digest_summary(
            [_make_item()],
            api_key="test-key",
            model="test-model",
        )
        assert isinstance(result, SummaryResult)
        assert result.summary_en is not None
        assert result.summary_zh is not None
        assert result.error is None

    @patch("worldlines.digest.summarizer._call_llm", side_effect=_mock_call_llm)
    def test_passes_correct_parameters(self, mock_llm):
        generate_digest_summary(
            [_make_item()],
            api_key="test-key",
            model="test-model",
            temperature=0.3,
            max_retries=5,
            timeout=120,
        )
        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args[1]
        assert call_kwargs["api_key"] == "test-key"
        assert call_kwargs["model"] == "test-model"
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_retries"] == 5
        assert call_kwargs["timeout"] == 120


# --- API errors ---


class TestApiError:
    @patch("worldlines.digest.summarizer._call_llm")
    def test_returns_error_on_api_failure(self, mock_llm):
        mock_llm.side_effect = Exception("Connection timeout")
        result = generate_digest_summary(
            [_make_item()],
            api_key="test-key",
            model="test-model",
        )
        assert result.summary_en is None
        assert result.summary_zh is None
        assert result.error is not None
        assert "api_error" in result.error
        assert "Connection timeout" in result.error


# --- JSON parse errors ---


class TestParseError:
    @patch("worldlines.digest.summarizer._call_llm")
    def test_returns_error_on_invalid_json(self, mock_llm):
        mock_llm.return_value = "This is not JSON"
        result = generate_digest_summary(
            [_make_item()],
            api_key="test-key",
            model="test-model",
        )
        assert result.summary_en is None
        assert result.summary_zh is None
        assert result.error is not None
        assert "parse_error" in result.error

    @patch("worldlines.digest.summarizer._call_llm")
    def test_handles_markdown_wrapped_response(self, mock_llm):
        mock_llm.return_value = f"```json\n{VALID_SUMMARY_RESPONSE}\n```"
        result = generate_digest_summary(
            [_make_item()],
            api_key="test-key",
            model="test-model",
        )
        assert result.summary_en is not None
        assert result.summary_zh is not None
        assert result.error is None


# --- Validation errors ---


class TestValidationError:
    @patch("worldlines.digest.summarizer._call_llm")
    def test_missing_summary_en(self, mock_llm):
        mock_llm.return_value = json.dumps({"summary_zh": "some text"})
        result = generate_digest_summary(
            [_make_item()],
            api_key="test-key",
            model="test-model",
        )
        assert result.error is not None
        assert "summary_en" in result.error

    @patch("worldlines.digest.summarizer._call_llm")
    def test_missing_summary_zh(self, mock_llm):
        mock_llm.return_value = json.dumps({"summary_en": "some text"})
        result = generate_digest_summary(
            [_make_item()],
            api_key="test-key",
            model="test-model",
        )
        assert result.error is not None
        assert "summary_zh" in result.error

    @patch("worldlines.digest.summarizer._call_llm")
    def test_empty_string_fields(self, mock_llm):
        mock_llm.return_value = json.dumps({"summary_en": "", "summary_zh": ""})
        result = generate_digest_summary(
            [_make_item()],
            api_key="test-key",
            model="test-model",
        )
        assert result.error is not None
        assert "non-empty" in result.error

    @patch("worldlines.digest.summarizer._call_llm")
    def test_summary_too_long(self, mock_llm):
        mock_llm.return_value = json.dumps({
            "summary_en": "x" * 1001,
            "summary_zh": "valid text",
        })
        result = generate_digest_summary(
            [_make_item()],
            api_key="test-key",
            model="test-model",
        )
        assert result.error is not None
        assert "1000" in result.error

    @patch("worldlines.digest.summarizer._call_llm")
    def test_forbidden_terms(self, mock_llm):
        mock_llm.return_value = json.dumps({
            "summary_en": "This is a bullish outlook for compute.",
            "summary_zh": "valid text",
        })
        result = generate_digest_summary(
            [_make_item()],
            api_key="test-key",
            model="test-model",
        )
        assert result.error is not None
        assert "bullish" in result.error


# --- validate_summary unit tests ---


class TestValidateSummary:
    def test_valid_data(self):
        data = {"summary_en": "Valid text.", "summary_zh": "Valid text."}
        assert validate_summary(data) == []

    def test_missing_fields(self):
        errors = validate_summary({})
        assert len(errors) == 2

    def test_non_string_field(self):
        errors = validate_summary({"summary_en": 123, "summary_zh": "ok"})
        assert any("non-empty string" in e for e in errors)

    def test_exceeds_max_length(self):
        errors = validate_summary({
            "summary_en": "x" * 1001,
            "summary_zh": "ok",
        })
        assert any("1000" in e for e in errors)

    def test_forbidden_term_detected(self):
        errors = validate_summary({
            "summary_en": "ok",
            "summary_zh": "This is bearish.",
        })
        assert any("bearish" in e for e in errors)


# --- JSON parsing ---


class TestParseJson:
    def test_parses_clean_json(self):
        data = _parse_json('{"key": "value"}')
        assert data == {"key": "value"}

    def test_strips_markdown_fences(self):
        raw = '```json\n{"key": "value"}\n```'
        data = _parse_json(raw)
        assert data == {"key": "value"}

    def test_raises_on_invalid_json(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            _parse_json("not json")


# --- Prompt formatting ---


class TestFormatPrompt:
    def test_includes_all_item_fields(self):
        item = _make_item(
            title="Test Title",
            summary="Test summary text.",
            dimensions=["compute_and_computational_paradigms", "capital_flows_and_business_models"],
            change_type="early_signal",
            importance="high",
        )
        prompt = format_summary_prompt([item])
        assert "Test Title" in prompt
        assert "Test summary text." in prompt
        assert "compute_and_computational_paradigms" in prompt
        assert "capital_flows_and_business_models" in prompt
        assert "early_signal" in prompt
        assert "HIGH" in prompt

    def test_includes_item_count(self):
        items = [_make_item(item_id=f"item-{i}") for i in range(3)]
        prompt = format_summary_prompt(items)
        assert "3 structural observations" in prompt

    def test_numbers_items(self):
        items = [
            _make_item(item_id="item-1", title="First"),
            _make_item(item_id="item-2", title="Second"),
        ]
        prompt = format_summary_prompt(items)
        assert "1. [HIGH] First" in prompt
        assert "2. [HIGH] Second" in prompt
