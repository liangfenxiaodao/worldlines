"""Cluster synthesis — produce a structural insight across a ticker's linked items."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from worldlines.analysis.classifier import _call_llm, _parse_json

logger = logging.getLogger(__name__)

_MAX_SYNTHESIS_CHARS = 600

_FORBIDDEN_TERMS = re.compile(
    r"\b(bullish|bearish|buy|sell|upside|downside|outperform|underperform)\b",
    re.IGNORECASE,
)

_SYSTEM_PROMPT = """\
You are a structural synthesis writer for a long-term trend intelligence system called Worldlines.

Given a set of observations that share structural exposure to the same ticker ({ticker}),
synthesize the pattern across them — not each item individually.

RULES:
- Synthesize ACROSS observations, not item by item
- Identify whether structural signals are converging, diverging, or evolving
- Neutral, factual, third person, present tense
- No predictions, opinions, or recommendations
- FORBIDDEN TERMS: bullish, bearish, buy, sell, upside, downside, outperform, underperform
- Maximum 600 characters

Respond in JSON only: {{"synthesis": "..."}}"""

_USER_PROMPT_TEMPLATE = """\
TICKER: {ticker}
OBSERVATIONS ({count} items):

{observations}

Synthesize these {count} observations into a single structural insight about {ticker}."""


@dataclass(frozen=True)
class SynthesisResult:
    synthesis: str | None
    error: dict | None = None


def synthesize_cluster(
    ticker: str,
    items: list[dict],
    *,
    api_key: str,
    model: str,
    temperature: float = 0.0,
    max_retries: int = 3,
    timeout: int = 60,
) -> SynthesisResult:
    """Call the LLM to synthesize a cluster of observations for a ticker.

    Each item in ``items`` must have keys: title, source_name, timestamp,
    change_type, time_horizon, summary.

    Returns a SynthesisResult with either a synthesis string or an error dict.
    """
    system_prompt = _SYSTEM_PROMPT.format(ticker=ticker)

    observation_lines = []
    for item in items:
        observation_lines.append(
            f"[{item['timestamp']}] {item['title']} ({item['source_name']})\n"
            f"  Change: {item['change_type']} | Horizon: {item['time_horizon']}\n"
            f"  Summary: {item['summary']}"
        )
    observations = "\n\n".join(observation_lines)

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        ticker=ticker,
        count=len(items),
        observations=observations,
    )

    try:
        raw_response = _call_llm(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout,
        )
    except Exception as exc:
        logger.exception("LLM API call failed for ticker cluster %s", ticker)
        return SynthesisResult(
            synthesis=None,
            error={"code": "api_error", "message": str(exc)},
        )

    try:
        data = _parse_json(raw_response)
    except ValueError as exc:
        logger.warning("Failed to parse LLM response for ticker %s: %s", ticker, exc)
        return SynthesisResult(
            synthesis=None,
            error={"code": "parse_error", "message": str(exc)},
        )

    synthesis_text = data.get("synthesis")
    if not isinstance(synthesis_text, str) or not synthesis_text.strip():
        return SynthesisResult(
            synthesis=None,
            error={"code": "empty_synthesis", "message": "LLM returned empty synthesis"},
        )

    # Truncate to limit rather than reject
    if len(synthesis_text) > _MAX_SYNTHESIS_CHARS:
        synthesis_text = synthesis_text[: _MAX_SYNTHESIS_CHARS - 1] + "\u2026"

    # Forbidden terms check
    match = _FORBIDDEN_TERMS.search(synthesis_text)
    if match:
        return SynthesisResult(
            synthesis=None,
            error={
                "code": "forbidden_term",
                "message": f"Forbidden term in synthesis: {match.group()}",
            },
        )

    return SynthesisResult(synthesis=synthesis_text)
