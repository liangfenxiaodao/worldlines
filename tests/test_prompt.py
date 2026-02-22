"""Tests for worldlines.analysis.prompt — prompt template and output validation."""

from __future__ import annotations

from worldlines.analysis.prompt import (
    SYSTEM_PROMPT,
    VALID_DIMENSIONS,
    format_user_prompt,
    validate_output,
)


def _valid_output(**overrides) -> dict:
    """Create a valid AnalyticalOutput dict with optional overrides."""
    base = {
        "dimensions": [
            {"dimension": "compute_and_computational_paradigms", "relevance": "primary"},
        ],
        "change_type": "reinforcing",
        "time_horizon": "medium_term",
        "summary": "TSMC reports capacity expansion for advanced nodes.",
        "importance": "medium",
        "key_entities": ["TSMC"],
    }
    base.update(overrides)
    return base


# --- System prompt ---


class TestSystemPrompt:
    def test_contains_role_framing(self):
        assert "structural analyst" in SYSTEM_PROMPT

    def test_contains_all_dimensions(self):
        for dim in VALID_DIMENSIONS:
            assert dim in SYSTEM_PROMPT

    def test_contains_constraints(self):
        assert "bullish" in SYSTEM_PROMPT
        assert "bearish" in SYSTEM_PROMPT
        assert "No predictions" in SYSTEM_PROMPT

    def test_contains_thin_content_handling(self):
        assert "THIN CONTENT HANDLING" in SYSTEM_PROMPT
        assert "Never return an empty dimensions array" in SYSTEM_PROMPT


# --- User prompt formatting ---


class TestFormatUserPrompt:
    def test_substitutes_fields(self):
        prompt = format_user_prompt(
            title="Test Title",
            source_name="Test Source",
            source_type="news",
            timestamp="2025-06-15T10:00:00Z",
            content="Article body here.",
        )
        assert "Test Title" in prompt
        assert "Test Source" in prompt
        assert "news" in prompt
        assert "2025-06-15T10:00:00Z" in prompt
        assert "Article body here." in prompt

    def test_contains_json_format_instructions(self):
        prompt = format_user_prompt(
            title="T", source_name="S", source_type="news",
            timestamp="2025-01-01", content="C",
        )
        assert '"dimensions"' in prompt
        assert '"change_type"' in prompt
        assert '"key_entities"' in prompt

    def test_truncates_long_content(self):
        long_content = "x" * 5000
        prompt = format_user_prompt(
            title="T", source_name="S", source_type="news",
            timestamp="2025-01-01", content=long_content,
        )
        # 2000 chars + "..." = 2003 chars of content in the prompt
        assert "x" * 2000 + "..." in prompt
        assert "x" * 2001 not in prompt

    def test_does_not_truncate_short_content(self):
        content = "x" * 2000
        prompt = format_user_prompt(
            title="T", source_name="S", source_type="news",
            timestamp="2025-01-01", content=content,
        )
        assert "x" * 2000 in prompt
        # Content at exactly the limit should not have truncation marker appended
        assert "x" * 2000 + "..." not in prompt

    def test_no_unresolved_placeholders(self):
        prompt = format_user_prompt(
            title="T", source_name="S", source_type="news",
            timestamp="2025-01-01", content="C",
        )
        # Should not contain any unresolved {field} placeholders
        # (double braces {{ }} in template resolve to literal braces)
        import re
        unresolved = re.findall(r"(?<!\{)\{[a-z_]+\}(?!\})", prompt)
        assert unresolved == []


# --- Output validation ---


class TestValidateOutput:
    def test_valid_output_no_errors(self):
        assert validate_output(_valid_output()) == []

    def test_multiple_dimensions(self):
        output = _valid_output(dimensions=[
            {"dimension": "compute_and_computational_paradigms", "relevance": "primary"},
            {"dimension": "capital_flows_and_business_models", "relevance": "secondary"},
        ])
        assert validate_output(output) == []

    # --- dimensions ---

    def test_empty_dimensions(self):
        errors = validate_output(_valid_output(dimensions=[]))
        assert any("dimensions" in e for e in errors)

    def test_missing_dimensions(self):
        output = _valid_output()
        del output["dimensions"]
        errors = validate_output(output)
        assert any("dimensions" in e for e in errors)

    def test_invalid_dimension_value(self):
        errors = validate_output(_valid_output(dimensions=[
            {"dimension": "invalid_dim", "relevance": "primary"},
        ]))
        assert any("invalid_dim" in e for e in errors)

    def test_invalid_relevance(self):
        errors = validate_output(_valid_output(dimensions=[
            {"dimension": "compute_and_computational_paradigms", "relevance": "high"},
        ]))
        assert any("relevance" in e for e in errors)

    def test_no_primary_dimension(self):
        errors = validate_output(_valid_output(dimensions=[
            {"dimension": "compute_and_computational_paradigms", "relevance": "secondary"},
        ]))
        assert any("primary" in e for e in errors)

    # --- change_type ---

    def test_invalid_change_type(self):
        errors = validate_output(_valid_output(change_type="bullish"))
        assert any("change_type" in e for e in errors)

    def test_all_valid_change_types(self):
        for ct in ["reinforcing", "friction", "early_signal", "neutral"]:
            assert validate_output(_valid_output(change_type=ct)) == []

    # --- time_horizon ---

    def test_invalid_time_horizon(self):
        errors = validate_output(_valid_output(time_horizon="immediate"))
        assert any("time_horizon" in e for e in errors)

    def test_all_valid_time_horizons(self):
        for th in ["short_term", "medium_term", "long_term"]:
            assert validate_output(_valid_output(time_horizon=th)) == []

    # --- summary ---

    def test_empty_summary(self):
        errors = validate_output(_valid_output(summary=""))
        assert any("summary" in e for e in errors)

    def test_summary_too_long(self):
        errors = validate_output(_valid_output(summary="x" * 501))
        assert any("500" in e for e in errors)

    def test_summary_exactly_500_chars(self):
        assert validate_output(_valid_output(summary="x" * 500)) == []

    def test_summary_forbidden_term_bullish(self):
        errors = validate_output(_valid_output(summary="This is a bullish signal."))
        assert any("bullish" in e for e in errors)

    def test_summary_forbidden_term_bearish(self):
        errors = validate_output(_valid_output(summary="A bearish outlook."))
        assert any("bearish" in e for e in errors)

    def test_summary_forbidden_term_case_insensitive(self):
        errors = validate_output(_valid_output(summary="BULLISH development"))
        assert any("bullish" in e for e in errors)

    def test_summary_forbidden_buy_sell(self):
        for term in ["buy", "sell"]:
            errors = validate_output(_valid_output(summary=f"Analysts say {term} now."))
            assert any(term in e for e in errors), f"Expected error for '{term}'"

    def test_summary_hold_is_allowed(self):
        """'hold' is common in central bank context (e.g. 'hold rates') and not forbidden."""
        errors = validate_output(_valid_output(summary="The Fed decides to hold rates steady."))
        assert errors == []

    def test_summary_forbidden_term_word_boundary(self):
        """Forbidden terms use word-boundary matching, not substring."""
        # "buyback" contains "buy" but should NOT trigger
        assert validate_output(_valid_output(summary="The company announced a buyback.")) == []
        # "buy" as standalone word should trigger
        errors = validate_output(_valid_output(summary="Analysts recommend to buy shares."))
        assert any("buy" in e for e in errors)

    def test_summary_forbidden_upside_downside(self):
        for term in ["upside", "downside", "outperform", "underperform"]:
            errors = validate_output(_valid_output(summary=f"Significant {term} expected."))
            assert any(term in e for e in errors), f"Expected error for '{term}'"

    # --- importance ---

    def test_invalid_importance(self):
        errors = validate_output(_valid_output(importance="critical"))
        assert any("importance" in e for e in errors)

    def test_all_valid_importance(self):
        for imp in ["low", "medium", "high"]:
            assert validate_output(_valid_output(importance=imp)) == []

    # --- key_entities ---

    def test_empty_key_entities(self):
        errors = validate_output(_valid_output(key_entities=[]))
        assert any("key_entities" in e for e in errors)

    def test_non_string_entities(self):
        errors = validate_output(_valid_output(key_entities=["TSMC", 123]))
        assert any("key_entities" in e for e in errors)

    def test_missing_key_entities(self):
        output = _valid_output()
        del output["key_entities"]
        errors = validate_output(output)
        assert any("key_entities" in e for e in errors)

    # --- multiple errors ---

    def test_multiple_errors_reported(self):
        errors = validate_output({
            "dimensions": [],
            "change_type": "invalid",
            "time_horizon": "invalid",
            "summary": "",
            "importance": "invalid",
            "key_entities": [],
        })
        assert len(errors) >= 5
