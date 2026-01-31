"""Normalization pipeline — validate raw items, produce NormalizedItems, persist."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from worldlines.ingestion.dedup import compute_dedup_hash
from worldlines.storage.connection import get_connection

logger = logging.getLogger(__name__)

VALID_SOURCE_TYPES = frozenset({
    "news", "filing", "transcript", "report",
    "research", "government", "policy", "industry", "other",
})


@dataclass(frozen=True)
class RawSourceItem:
    """Raw item emitted by a source adapter."""

    source_name: str
    source_type: str
    title: str
    content: str
    url: str | None = None
    published_at: str | None = None


@dataclass(frozen=True)
class NormalizedItem:
    """Canonical internal representation of an ingested item."""

    id: str
    title: str
    source_name: str
    source_type: str
    timestamp: str
    content: str
    canonical_link: str | None
    ingested_at: str
    dedup_hash: str


def _validate_raw_item(raw: RawSourceItem) -> list[str]:
    """Validate a RawSourceItem against the input contract. Returns a list of errors."""
    errors: list[str] = []
    if not raw.title or not raw.title.strip():
        errors.append("title is required and must be non-empty")
    if not raw.source_name or not raw.source_name.strip():
        errors.append("source_name is required and must be non-empty")
    if not raw.source_type or not raw.source_type.strip():
        errors.append("source_type is required and must be non-empty")
    elif raw.source_type not in VALID_SOURCE_TYPES:
        errors.append(
            f"source_type '{raw.source_type}' is not valid; "
            f"must be one of: {', '.join(sorted(VALID_SOURCE_TYPES))}"
        )
    if not raw.content or not raw.content.strip():
        errors.append("content is required and must be non-empty")
    if raw.published_at is not None:
        try:
            datetime.fromisoformat(raw.published_at)
        except ValueError:
            errors.append(f"published_at '{raw.published_at}' is not valid ISO 8601")
    return errors


def normalize(raw: RawSourceItem) -> NormalizedItem:
    """Transform a RawSourceItem into a NormalizedItem.

    Validates required fields, generates a UUID, computes the dedup hash,
    and falls back to ingestion time if published_at is missing.

    Raises ValueError if validation fails.
    """
    errors = _validate_raw_item(raw)
    if errors:
        raise ValueError(f"Invalid RawSourceItem: {'; '.join(errors)}")

    now = datetime.now(timezone.utc).isoformat()
    timestamp = raw.published_at if raw.published_at is not None else now

    return NormalizedItem(
        id=str(uuid.uuid4()),
        title=raw.title,
        source_name=raw.source_name,
        source_type=raw.source_type,
        timestamp=timestamp,
        content=raw.content,
        canonical_link=raw.url,
        ingested_at=now,
        dedup_hash=compute_dedup_hash(raw.title, raw.source_name, raw.content),
    )


def persist_item(item: NormalizedItem, database_path: str) -> None:
    """Insert a NormalizedItem into the Items Store."""
    with get_connection(database_path) as conn:
        conn.execute(
            "INSERT INTO items "
            "(id, title, source_name, source_type, timestamp, content, "
            "canonical_link, ingested_at, dedup_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item.id,
                item.title,
                item.source_name,
                item.source_type,
                item.timestamp,
                item.content,
                item.canonical_link,
                item.ingested_at,
                item.dedup_hash,
            ),
        )
    logger.info("Persisted item %s (%s)", item.id, item.title)
