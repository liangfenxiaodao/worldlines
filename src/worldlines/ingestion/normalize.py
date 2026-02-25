"""Normalization pipeline — validate raw items, produce NormalizedItems, persist."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from worldlines.ingestion.dedup import compute_dedup_hash, compute_title_shingle_similarity
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


@dataclass(frozen=True)
class NormalizationResult:
    """Result of the normalize-and-deduplicate pipeline."""

    status: str  # "new" or "duplicate"
    item: NormalizedItem
    duplicate_of: str | None = None  # canonical item ID if duplicate


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


def ingest_item(
    raw: RawSourceItem,
    database_path: str,
    similarity_threshold: float = 0.0,
    similarity_window_hours: int = 48,
) -> NormalizationResult:
    """Normalize a raw item and deduplicate against the Items Store.

    1. Normalize the raw item (validate, generate UUID, compute dedup hash).
    2. Check the Items Store for an existing item with the same dedup_hash.
    3. If duplicate: record a DeduplicationRecord and return status "duplicate".
    4. If new: persist the item and return status "new".
    """
    item = normalize(raw)

    with get_connection(database_path) as conn:
        existing = conn.execute(
            "SELECT id FROM items WHERE dedup_hash = ?",
            (item.dedup_hash,),
        ).fetchone()

        if existing is not None:
            canonical_id = existing["id"]
            conn.execute(
                "INSERT INTO deduplication_records "
                "(canonical_item_id, duplicate_item_ids, deduped_at, method) "
                "VALUES (?, ?, ?, ?)",
                (
                    canonical_id,
                    json.dumps([item.id]),
                    datetime.now(timezone.utc).isoformat(),
                    "hash_exact",
                ),
            )
            logger.info(
                "Duplicate detected: %s is duplicate of %s", item.id, canonical_id
            )
            return NormalizationResult(
                status="duplicate", item=item, duplicate_of=canonical_id
            )

        # Similarity dedup (only when threshold > 0)
        if similarity_threshold > 0.0:
            window_cutoff = (
                datetime.now(timezone.utc) - timedelta(hours=similarity_window_hours)
            ).isoformat()
            recent_rows = conn.execute(
                "SELECT id, title FROM items WHERE ingested_at >= ? "
                "ORDER BY ingested_at DESC LIMIT 200",
                (window_cutoff,),
            ).fetchall()
            for recent in recent_rows:
                score = compute_title_shingle_similarity(item.title, recent["title"])
                if score >= similarity_threshold:
                    canonical_id = recent["id"]
                    conn.execute(
                        "INSERT INTO deduplication_records "
                        "(canonical_item_id, duplicate_item_ids, deduped_at, method) "
                        "VALUES (?, ?, ?, ?)",
                        (
                            canonical_id,
                            json.dumps([item.id]),
                            datetime.now(timezone.utc).isoformat(),
                            "content_similarity",
                        ),
                    )
                    logger.info(
                        "Near-duplicate: '%s' ~ '%s' (score=%.2f)",
                        item.title, recent["title"], score,
                    )
                    return NormalizationResult(
                        status="duplicate", item=item, duplicate_of=canonical_id
                    )

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

    logger.info("Ingested new item %s (%s)", item.id, item.title)
    return NormalizationResult(status="new", item=item)
