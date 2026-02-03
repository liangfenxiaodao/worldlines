"""AI classification pipeline — call LLM, parse response, persist analysis."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import anthropic

from worldlines.analysis.prompt import (
    SYSTEM_PROMPT,
    format_user_prompt,
    validate_output,
)
from worldlines.ingestion.normalize import NormalizedItem
from worldlines.storage.connection import get_connection

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisResult:
    """Result of the classification pipeline."""

    analysis: dict | None
    error: dict | None = None


def classify_item(
    item: NormalizedItem,
    *,
    api_key: str,
    model: str,
    analysis_version: str,
    database_path: str,
    temperature: float = 0.0,
    max_retries: int = 3,
    timeout: int = 60,
) -> AnalysisResult:
    """Classify a NormalizedItem using the LLM and persist the result.

    1. Format the prompt with item fields.
    2. Call the Anthropic API.
    3. Parse and validate the JSON response.
    4. Persist the AnalyticalOutput to the analyses table.
    5. Return the result.

    On failure (API error, invalid JSON, validation failure), returns an
    AnalysisResult with error details. The NormalizedItem is retained in
    the Items Store for retry.
    """
    user_prompt = format_user_prompt(
        title=item.title,
        source_name=item.source_name,
        source_type=item.source_type,
        timestamp=item.timestamp,
        content=item.content,
    )

    # Call LLM
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
        logger.exception("LLM API call failed for item %s", item.id)
        return AnalysisResult(
            analysis=None,
            error={"code": "api_error", "message": str(exc)},
        )

    # Parse JSON
    try:
        data = _parse_json(raw_response)
    except ValueError as exc:
        logger.warning("Failed to parse LLM response for item %s: %s", item.id, exc)
        return AnalysisResult(
            analysis=None,
            error={"code": "parse_error", "message": str(exc)},
        )

    # Validate
    errors = validate_output(data)
    if errors:
        logger.warning(
            "Validation failed for item %s: %s", item.id, "; ".join(errors)
        )
        return AnalysisResult(
            analysis=None,
            error={"code": "classification_uncertain", "message": "; ".join(errors)},
        )

    # Build analysis record
    analysis_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    analysis = {
        "id": analysis_id,
        "item_id": item.id,
        "dimensions": data["dimensions"],
        "change_type": data["change_type"],
        "time_horizon": data["time_horizon"],
        "summary": data["summary"],
        "importance": data["importance"],
        "key_entities": data["key_entities"],
        "analyzed_at": now,
        "analysis_version": analysis_version,
    }

    # Persist
    _persist_analysis(analysis, database_path)
    logger.info("Analyzed item %s → %s (%s)", item.id, analysis_id, data["importance"])

    return AnalysisResult(analysis=analysis)


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
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc


def _persist_analysis(analysis: dict, database_path: str) -> None:
    """Insert an AnalyticalOutput into the analyses table."""
    with get_connection(database_path) as conn:
        conn.execute(
            "INSERT INTO analyses "
            "(id, item_id, dimensions, change_type, time_horizon, summary, "
            "importance, key_entities, analyzed_at, analysis_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                analysis["id"],
                analysis["item_id"],
                json.dumps(analysis["dimensions"]),
                analysis["change_type"],
                analysis["time_horizon"],
                analysis["summary"],
                analysis["importance"],
                json.dumps(analysis["key_entities"]),
                analysis["analyzed_at"],
                analysis["analysis_version"],
            ),
        )
