"""Tests for worldlines.exposure.prompt — prompt template and validation."""

from __future__ import annotations

from worldlines.exposure.prompt import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    VALID_BUSINESS_ROLES,
    VALID_CONFIDENCE,
    VALID_EXPOSURE_STRENGTHS,
    VALID_EXPOSURE_TYPES,
    format_user_prompt,
    validate_output,
)


# --- System Prompt ---


class TestSystemPrompt:
    def test_contains_exposure_taxonomy(self):
        assert "exposure_type" in SYSTEM_PROMPT
        assert "business_role" in SYSTEM_PROMPT
        assert "exposure_strength" in SYSTEM_PROMPT
        assert "confidence" in SYSTEM_PROMPT

    def test_contains_role_instruction(self):
        assert "structural exposure mapper" in SYSTEM_PROMPT

    def test_contains_forbidden_terms(self):
        assert "bullish" in SYSTEM_PROMPT
        assert "bearish" in SYSTEM_PROMPT

    def test_contains_ticker_rules(self):
        assert "ticker" in SYSTEM_PROMPT.lower()
        assert "publicly listed" in SYSTEM_PROMPT

    def test_contains_when_to_skip(self):
        assert "skipped_reason" in SYSTEM_PROMPT


# --- User Prompt ---


class TestUserPrompt:
    def test_template_has_all_placeholders(self):
        placeholders = [
            "summary", "dimensions", "change_type", "time_horizon",
            "importance", "key_entities", "title", "source_name", "source_type",
        ]
        for p in placeholders:
            assert f"{{{p}}}" in USER_PROMPT_TEMPLATE

    def test_format_user_prompt(self):
        result = format_user_prompt(
            summary="Test summary",
            dimensions="compute_and_computational_paradigms",
            change_type="reinforcing",
            time_horizon="medium_term",
            importance="high",
            key_entities="NVIDIA, TSMC",
            title="Test Title",
            source_name="Test Source",
            source_type="news",
        )
        assert "Test summary" in result
        assert "Test Title" in result
        assert "NVIDIA, TSMC" in result
        assert "compute_and_computational_paradigms" in result


# --- Validation Constants ---


class TestValidationConstants:
    def test_exposure_types(self):
        assert VALID_EXPOSURE_TYPES == {"direct", "indirect", "contextual"}

    def test_business_roles(self):
        assert "infrastructure_operator" in VALID_BUSINESS_ROLES
        assert "other" in VALID_BUSINESS_ROLES
        assert len(VALID_BUSINESS_ROLES) == 7

    def test_exposure_strengths(self):
        assert VALID_EXPOSURE_STRENGTHS == {"core", "material", "peripheral"}

    def test_confidence_levels(self):
        assert VALID_CONFIDENCE == {"high", "medium", "low"}


# --- Validation ---


def _valid_exposure():
    return {
        "ticker": "AAPL",
        "exposure_type": "direct",
        "business_role": "downstream_adopter",
        "exposure_strength": "core",
        "confidence": "high",
        "dimensions_implicated": ["compute_and_computational_paradigms"],
        "rationale": "Apple integrates custom silicon for AI inference workloads.",
    }


def _valid_output(exposures=None, skipped_reason=None):
    if exposures is None:
        exposures = [_valid_exposure()]
    return {"exposures": exposures, "skipped_reason": skipped_reason}


class TestValidateOutput:
    def test_valid_single_exposure(self):
        assert validate_output(_valid_output()) == []

    def test_valid_multiple_exposures(self):
        data = _valid_output(exposures=[
            _valid_exposure(),
            {**_valid_exposure(), "ticker": "NVDA", "confidence": "medium"},
        ])
        assert validate_output(data) == []

    def test_valid_empty_with_skipped_reason(self):
        data = _valid_output(
            exposures=[],
            skipped_reason="Analysis discusses abstract theoretical concepts only.",
        )
        assert validate_output(data) == []

    def test_exposures_must_be_list(self):
        errs = validate_output({"exposures": "not a list"})
        assert any("must be a list" in e for e in errs)

    def test_empty_without_skipped_reason(self):
        data = _valid_output(exposures=[], skipped_reason=None)
        errs = validate_output(data)
        assert any("skipped_reason is required" in e for e in errs)

    def test_non_empty_with_skipped_reason(self):
        data = _valid_output(
            exposures=[_valid_exposure()],
            skipped_reason="should not be here",
        )
        errs = validate_output(data)
        assert any("must be null" in e for e in errs)

    def test_invalid_exposure_type(self):
        exp = {**_valid_exposure(), "exposure_type": "tangential"}
        errs = validate_output(_valid_output(exposures=[exp]))
        assert any("exposure_type" in e for e in errs)

    def test_invalid_business_role(self):
        exp = {**_valid_exposure(), "business_role": "competitor"}
        errs = validate_output(_valid_output(exposures=[exp]))
        assert any("business_role" in e for e in errs)

    def test_invalid_exposure_strength(self):
        exp = {**_valid_exposure(), "exposure_strength": "strong"}
        errs = validate_output(_valid_output(exposures=[exp]))
        assert any("exposure_strength" in e for e in errs)

    def test_invalid_confidence(self):
        exp = {**_valid_exposure(), "confidence": "very_high"}
        errs = validate_output(_valid_output(exposures=[exp]))
        assert any("confidence" in e for e in errs)

    def test_empty_ticker(self):
        exp = {**_valid_exposure(), "ticker": ""}
        errs = validate_output(_valid_output(exposures=[exp]))
        assert any("ticker" in e for e in errs)

    def test_empty_dimensions_implicated(self):
        exp = {**_valid_exposure(), "dimensions_implicated": []}
        errs = validate_output(_valid_output(exposures=[exp]))
        assert any("dimensions_implicated" in e for e in errs)

    def test_invalid_dimension(self):
        exp = {**_valid_exposure(), "dimensions_implicated": ["fake_dimension"]}
        errs = validate_output(_valid_output(exposures=[exp]))
        assert any("invalid dimension" in e for e in errs)

    def test_rationale_too_long(self):
        exp = {**_valid_exposure(), "rationale": "x" * 301}
        errs = validate_output(_valid_output(exposures=[exp]))
        assert any("300 characters" in e for e in errs)

    def test_rationale_empty(self):
        exp = {**_valid_exposure(), "rationale": ""}
        errs = validate_output(_valid_output(exposures=[exp]))
        assert any("rationale" in e for e in errs)

    def test_rationale_forbidden_terms(self):
        exp = {**_valid_exposure(), "rationale": "This is bullish for the company."}
        errs = validate_output(_valid_output(exposures=[exp]))
        assert any("forbidden term" in e for e in errs)

    def test_rationale_forbidden_term_bearish(self):
        exp = {**_valid_exposure(), "rationale": "The outlook is bearish for this sector."}
        errs = validate_output(_valid_output(exposures=[exp]))
        assert any("bearish" in e for e in errs)

    def test_non_dict_exposure_entry(self):
        errs = validate_output(_valid_output(exposures=["not a dict"]))
        assert any("must be an object" in e for e in errs)
