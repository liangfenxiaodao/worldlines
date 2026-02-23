"""Exposure mapping pipeline — call LLM, parse response, persist exposures."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from worldlines.analysis.classifier import _call_llm, _parse_json
from worldlines.exposure.prompt import (
    SYSTEM_PROMPT,
    format_user_prompt,
    validate_output,
)
from worldlines.storage.connection import get_connection

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExposureResult:
    """Result of the exposure mapping pipeline."""

    exposure_record: dict | None
    skipped_reason: str | None = None
    error: dict | None = None


def map_exposures(
    analysis: dict,
    item: dict,
    *,
    api_key: str,
    model: str,
    exposure_mapping_version: str,
    database_path: str,
    temperature: float = 0.0,
    max_retries: int = 3,
    timeout: int = 60,
) -> ExposureResult:
    """Map an analysis to structural exposures using the LLM.

    1. Format the prompt with analysis + item fields.
    2. Call the Anthropic API.
    3. Parse and validate the JSON response.
    4. Persist the exposure record.
    5. Return the result.
    """
    # Format dimensions for prompt
    dims = analysis.get("dimensions")
    if isinstance(dims, str):
        dims = json.loads(dims)
    dims_str = ", ".join(d["dimension"] for d in dims if isinstance(d, dict))

    key_entities = analysis.get("key_entities")
    if isinstance(key_entities, str):
        key_entities = json.loads(key_entities)
    entities_str = ", ".join(key_entities) if key_entities else ""

    user_prompt = format_user_prompt(
        summary=analysis["summary"],
        dimensions=dims_str,
        change_type=analysis["change_type"],
        time_horizon=analysis["time_horizon"],
        importance=analysis["importance"],
        key_entities=entities_str,
        title=item["title"],
        source_name=item["source_name"],
        source_type=item["source_type"],
    )

    analysis_id = analysis["analysis_id"]

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
        logger.exception("LLM API call failed for analysis %s", analysis_id)
        return ExposureResult(
            exposure_record=None,
            error={"code": "api_error", "message": str(exc)},
        )

    # Parse JSON
    try:
        data = _parse_json(raw_response)
    except ValueError as exc:
        logger.warning(
            "Failed to parse LLM response for analysis %s: %s", analysis_id, exc
        )
        return ExposureResult(
            exposure_record=None,
            error={"code": "parse_error", "message": str(exc)},
        )

    # Validate
    errors = validate_output(data)
    if errors:
        logger.warning(
            "Validation failed for analysis %s: %s", analysis_id, "; ".join(errors)
        )
        return ExposureResult(
            exposure_record=None,
            error={"code": "mapping_uncertain", "message": "; ".join(errors)},
        )

    # Build exposure record
    exposure_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    skipped_reason = data.get("skipped_reason")

    record = {
        "id": exposure_id,
        "analysis_id": analysis_id,
        "exposures": data["exposures"],
        "skipped_reason": skipped_reason,
        "mapped_at": now,
    }

    # Persist
    _persist_exposure(record, database_path)
    logger.info(
        "Mapped analysis %s → %s (%d exposures%s)",
        analysis_id,
        exposure_id,
        len(data["exposures"]),
        f", skipped: {skipped_reason}" if skipped_reason else "",
    )

    return ExposureResult(exposure_record=record, skipped_reason=skipped_reason)


def _persist_exposure(record: dict, database_path: str) -> None:
    """Insert an exposure record into the exposures table."""
    with get_connection(database_path) as conn:
        conn.execute(
            "INSERT INTO exposures "
            "(id, analysis_id, exposures, skipped_reason, mapped_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                record["id"],
                record["analysis_id"],
                json.dumps(record["exposures"]),
                record["skipped_reason"],
                record["mapped_at"],
            ),
        )
