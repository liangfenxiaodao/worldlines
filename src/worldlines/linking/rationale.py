"""LLM-generated rationale for temporal links."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from worldlines.analysis.classifier import _call_llm, _parse_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a structural analyst for a long-term trend intelligence system.
Your task is to write a neutral, factual 1-2 sentence explanation of why two
signals are structurally related. Focus on the shared structural theme, not
on short-term events. Do not make predictions. Do not use hype language.
Respond with JSON: {"rationale": "..."}"""


@dataclass(frozen=True)
class RationaleResult:
    """Result of the rationale generation pipeline."""

    rationale: str | None
    error: dict | None = None


def _build_prompt(
    source_item: dict,
    target_item: dict,
    shared_tickers: list[str],
    link_type: str,
) -> str:
    """Format the user prompt for rationale generation."""
    tickers_str = ", ".join(sorted(shared_tickers))
    return (
        f"Link type: {link_type}\n"
        f"Shared instruments: {tickers_str}\n\n"
        f"Signal A (newer):\n"
        f"  Title: {source_item.get('title', '')}\n"
        f"  Summary: {source_item.get('summary', '')}\n"
        f"  Dimensions: {source_item.get('dimensions', '')}\n"
        f"  Change type: {source_item.get('change_type', '')}\n"
        f"  Timestamp: {source_item.get('timestamp', '')}\n\n"
        f"Signal B (older):\n"
        f"  Title: {target_item.get('title', '')}\n"
        f"  Summary: {target_item.get('summary', '')}\n"
        f"  Dimensions: {target_item.get('dimensions', '')}\n"
        f"  Change type: {target_item.get('change_type', '')}\n"
        f"  Timestamp: {target_item.get('timestamp', '')}\n\n"
        "Write a neutral 1-2 sentence explanation of the structural relationship "
        "between these two signals."
    )


def generate_link_rationale(
    source_item: dict,
    target_item: dict,
    shared_tickers: list[str],
    link_type: str,
    *,
    api_key: str,
    model: str,
    rationale_version: str,
    temperature: float = 0.0,
    max_retries: int = 3,
    timeout: int = 60,
) -> RationaleResult:
    """Generate an LLM rationale for a temporal link.

    Returns RationaleResult with rationale=None and error details on any failure.
    Never raises — graceful degradation keeps the mechanical rationale intact.
    """
    user_prompt = _build_prompt(source_item, target_item, shared_tickers, link_type)

    try:
        raw_response = _call_llm(
            api_key=api_key,
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout,
        )
    except Exception as exc:
        logger.warning("LLM API call failed for link rationale: %s", exc)
        return RationaleResult(
            rationale=None,
            error={"code": "api_error", "message": str(exc)},
        )

    try:
        data = _parse_json(raw_response)
    except ValueError as exc:
        logger.warning("Failed to parse LLM rationale response: %s", exc)
        return RationaleResult(
            rationale=None,
            error={"code": "parse_error", "message": str(exc)},
        )

    rationale = data.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        logger.warning("LLM rationale response missing or empty 'rationale' key")
        return RationaleResult(
            rationale=None,
            error={"code": "missing_rationale", "message": "rationale key missing or empty"},
        )

    return RationaleResult(rationale=rationale)
