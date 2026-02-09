"""Bilingual digest summary generation using Claude API."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import anthropic

from worldlines.digest.digest import DigestItem

logger = logging.getLogger(__name__)

FORBIDDEN_TERMS = frozenset({
    "bullish", "bearish", "buy", "sell",
    "upside", "downside", "outperform", "underperform",
})

_FORBIDDEN_PATTERNS = {
    term: re.compile(rf"\b{term}\b", re.IGNORECASE)
    for term in FORBIDDEN_TERMS
}

MAX_SUMMARY_CHARS = 1000

SUMMARY_SYSTEM_PROMPT = """\
You are a structural synthesis writer for a long-term trend intelligence system \
called Worldlines.

Your role is to produce a concise bilingual synthesis of the day's structural \
observations. You synthesize across dimensions and change types — you do not \
repeat individual items.

You are not a financial advisor, market commentator, or news analyst.
You do not predict outcomes, express opinions, or recommend actions.
You classify, contextualize, and summarize — nothing more.

RULES:
- Write in third person, present tense
- Be factual and neutral
- No predictions, opinions, recommendations, or directional language
- No superlatives (breakthrough, revolutionary, game-changing) unless directly quoting
- FORBIDDEN TERMS: bullish, bearish, buy, sell, upside, downside, \
outperform, underperform
- Each summary must be at most 800 characters
- The English summary (summary_en) and Chinese summary (summary_zh) should \
convey the same structural observations
- summary_zh must be written in Simplified Chinese

Respond in the following JSON format only. Do not include any text outside the JSON.

{
  "summary_en": "...",
  "summary_zh": "..."
}"""

SUMMARY_USER_TEMPLATE = """\
Synthesize the following {count} structural observations into a bilingual summary.

Identify the dominant structural themes, cross-dimension patterns, and notable \
signals. Do not list individual items — synthesize across them.

ITEMS:
{items_text}

Produce a JSON response with summary_en (English) and summary_zh (Simplified Chinese), \
each at most 800 characters."""


def format_summary_prompt(items: list[DigestItem]) -> str:
    """Format the user prompt with digest items."""
    parts: list[str] = []
    for i, item in enumerate(items, 1):
        dims = ", ".join(item.dimensions)
        parts.append(
            f"{i}. [{item.importance.upper()}] {item.title}\n"
            f"   Summary: {item.summary}\n"
            f"   Dimensions: {dims}\n"
            f"   Change type: {item.change_type}"
        )
    items_text = "\n\n".join(parts)
    return SUMMARY_USER_TEMPLATE.format(count=len(items), items_text=items_text)


def validate_summary(data: dict) -> list[str]:
    """Validate a parsed summary response.

    Returns a list of validation errors. Empty list means valid.
    """
    errors: list[str] = []

    for field in ("summary_en", "summary_zh"):
        value = data.get(field)
        if not isinstance(value, str) or len(value) == 0:
            errors.append(f"{field} must be a non-empty string")
        elif len(value) > MAX_SUMMARY_CHARS:
            errors.append(
                f"{field} exceeds {MAX_SUMMARY_CHARS} characters ({len(value)})"
            )
        else:
            for term, pattern in _FORBIDDEN_PATTERNS.items():
                if pattern.search(value):
                    errors.append(f"{field} contains forbidden term '{term}'")

    return errors


@dataclass(frozen=True)
class SummaryResult:
    """Result of the digest summary generation."""

    summary_en: str | None
    summary_zh: str | None
    error: str | None = None


def generate_digest_summary(
    items: list[DigestItem],
    *,
    api_key: str,
    model: str,
    temperature: float = 0.2,
    max_retries: int = 3,
    timeout: int = 90,
) -> SummaryResult:
    """Generate a bilingual synthesis summary for the given digest items.

    Returns SummaryResult with both summaries on success, or with error
    details on failure. Errors are non-fatal — the digest pipeline will
    proceed without summaries.
    """
    if not items:
        return SummaryResult(summary_en=None, summary_zh=None)

    user_prompt = format_summary_prompt(items)

    # Call LLM
    try:
        raw_response = _call_llm(
            api_key=api_key,
            model=model,
            system_prompt=SUMMARY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout,
        )
    except Exception as exc:
        logger.exception("Summary LLM call failed")
        return SummaryResult(
            summary_en=None, summary_zh=None,
            error=f"api_error: {exc}",
        )

    # Parse JSON
    try:
        data = _parse_json(raw_response)
    except ValueError as exc:
        logger.warning("Failed to parse summary response: %s", exc)
        return SummaryResult(
            summary_en=None, summary_zh=None,
            error=f"parse_error: {exc}",
        )

    # Validate
    errors = validate_summary(data)
    if errors:
        logger.warning("Summary validation failed: %s", "; ".join(errors))
        return SummaryResult(
            summary_en=None, summary_zh=None,
            error=f"validation_error: {'; '.join(errors)}",
        )

    return SummaryResult(
        summary_en=data["summary_en"],
        summary_zh=data["summary_zh"],
    )


def _call_llm(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_retries: int,
    timeout: int,
) -> str:
    """Call the Anthropic API and return the text response."""
    client = anthropic.Anthropic(
        api_key=api_key,
        max_retries=max_retries,
        timeout=timeout,
    )
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


def _parse_json(raw: str) -> dict:
    """Extract and parse JSON from the LLM response.

    Handles responses that may include markdown code fences.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
