"""Digest orchestrator — query, aggregate, render, send, persist."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from worldlines.digest.renderer import (
    chunk_message,
    render_digest_html,
    render_empty_day_html,
)
from worldlines.digest.telegram import send_messages
from worldlines.storage.connection import get_connection

logger = logging.getLogger(__name__)

IMPORTANCE_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class DigestItem:
    """A single item prepared for digest display."""

    item_id: str
    analysis_id: str
    title: str
    summary: str
    dimensions: list[str]
    change_type: str
    time_horizon: str
    importance: str
    canonical_link: str | None


@dataclass(frozen=True)
class DigestData:
    """Aggregated data ready for rendering."""

    digest_date: str
    total_analyzed: int
    item_count: int
    dimension_breakdown: dict[str, int]
    change_type_distribution: dict[str, int]
    items: list[DigestItem] = field(default_factory=list)


@dataclass(frozen=True)
class DigestResult:
    """Pipeline output returned to the caller."""

    digest_record: dict | None
    delivery_status: str  # "sent" | "empty_day" | "failed"
    error: str | None = None


def generate_digest(
    digest_date: str,
    since: str,
    *,
    database_path: str,
    bot_token: str,
    chat_id: str,
    parse_mode: str = "HTML",
    max_items: int = 20,
    max_retries: int = 3,
) -> DigestResult:
    """Generate and deliver the daily digest.

    1. Query analyses within the time window.
    2. Aggregate into DigestData.
    3. Render HTML message.
    4. Chunk and send via Telegram.
    5. Persist digest record.
    6. Return result.
    """
    # Compute end of window: day after digest_date
    next_day = date.fromisoformat(digest_date) + timedelta(days=1)
    until = next_day.isoformat()

    # Query
    rows = _query_analyses(database_path, since, until)
    total_analyzed = len(rows)

    # Aggregate
    data = _aggregate(rows, digest_date, total_analyzed, max_items)

    # Empty day
    if data.item_count == 0:
        message_text = render_empty_day_html(digest_date)
        chunks = chunk_message(message_text)
        results = send_messages(
            bot_token, chat_id, chunks, parse_mode=parse_mode, max_retries=max_retries,
        )
        message_ids = [r.message_id for r in results if r.ok]
        record = _build_record(data, message_text, message_ids)
        try:
            _persist_digest(record, database_path)
        except sqlite3.IntegrityError as exc:
            return DigestResult(
                digest_record=None, delivery_status="failed",
                error=f"Duplicate digest date: {exc}",
            )
        return DigestResult(digest_record=record, delivery_status="empty_day")

    # Render
    message_text = render_digest_html(data)
    chunks = chunk_message(message_text)

    # Send
    results = send_messages(
        bot_token, chat_id, chunks, parse_mode=parse_mode, max_retries=max_retries,
    )
    all_ok = all(r.ok for r in results)
    message_ids = [r.message_id for r in results if r.ok]

    # Build record
    record = _build_record(data, message_text, message_ids)

    # Persist (even on send failure)
    try:
        _persist_digest(record, database_path)
    except sqlite3.IntegrityError as exc:
        return DigestResult(
            digest_record=None, delivery_status="failed",
            error=f"Duplicate digest date: {exc}",
        )

    if not all_ok:
        first_error = next((r.error for r in results if not r.ok), "Unknown error")
        return DigestResult(
            digest_record=record, delivery_status="failed", error=first_error,
        )

    return DigestResult(digest_record=record, delivery_status="sent")


def _query_analyses(
    database_path: str,
    since: str,
    until: str,
) -> list[dict]:
    """Query analyses joined with items within the time window.

    Returns rows ordered by importance (high first) then analyzed_at descending.
    """
    sql = (
        "SELECT a.id AS analysis_id, a.item_id, a.dimensions, a.change_type, "
        "a.time_horizon, a.summary, a.importance, a.analyzed_at, "
        "i.title, i.canonical_link "
        "FROM analyses a "
        "JOIN items i ON a.item_id = i.id "
        "WHERE a.analyzed_at >= ? AND a.analyzed_at < ? "
        "ORDER BY "
        "  CASE a.importance "
        "    WHEN 'high' THEN 0 "
        "    WHEN 'medium' THEN 1 "
        "    WHEN 'low' THEN 2 "
        "  END, "
        "  a.analyzed_at DESC"
    )
    with get_connection(database_path) as conn:
        cursor = conn.execute(sql, (since, until))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _aggregate(
    rows: list[dict],
    digest_date: str,
    total_analyzed: int,
    max_items: int,
) -> DigestData:
    """Build DigestData from query rows.

    Filters to medium + high importance, caps at max_items.
    Dimension and change-type counts cover ALL rows (not just filtered).
    """
    # Count dimensions and change types across all rows
    dimension_counts: dict[str, int] = {}
    change_type_counts: dict[str, int] = {}

    for row in rows:
        dims = json.loads(row["dimensions"])
        for dim_entry in dims:
            dim_name = dim_entry["dimension"]
            dimension_counts[dim_name] = dimension_counts.get(dim_name, 0) + 1
        ct = row["change_type"]
        change_type_counts[ct] = change_type_counts.get(ct, 0) + 1

    # Filter to medium + high importance
    filtered = [r for r in rows if r["importance"] in ("high", "medium")]
    capped = filtered[:max_items]

    items = []
    for row in capped:
        dims = json.loads(row["dimensions"])
        dim_names = [d["dimension"] for d in dims]
        items.append(
            DigestItem(
                item_id=row["item_id"],
                analysis_id=row["analysis_id"],
                title=row["title"],
                summary=row["summary"],
                dimensions=dim_names,
                change_type=row["change_type"],
                time_horizon=row["time_horizon"],
                importance=row["importance"],
                canonical_link=row["canonical_link"],
            )
        )

    return DigestData(
        digest_date=digest_date,
        total_analyzed=total_analyzed,
        item_count=len(items),
        dimension_breakdown=dimension_counts,
        change_type_distribution=change_type_counts,
        items=items,
    )


def _build_record(
    data: DigestData,
    message_text: str,
    message_ids: list[int],
) -> dict:
    """Build a digest record dict ready for persistence."""
    high_items = [
        {"item_id": item.item_id, "analysis_id": item.analysis_id}
        for item in data.items
        if item.importance == "high"
    ]
    return {
        "id": str(uuid.uuid4()),
        "digest_date": data.digest_date,
        "item_count": data.item_count,
        "dimension_breakdown": data.dimension_breakdown,
        "change_type_distribution": data.change_type_distribution,
        "high_importance_items": high_items,
        "summary_en": None,
        "summary_zh": None,
        "message_text": message_text,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "telegram_message_ids": message_ids,
    }


def _persist_digest(record: dict, database_path: str) -> None:
    """Insert a digest record into the digests table."""
    with get_connection(database_path) as conn:
        conn.execute(
            "INSERT INTO digests "
            "(id, digest_date, item_count, dimension_breakdown, "
            "change_type_distribution, high_importance_items, "
            "summary_en, summary_zh, "
            "message_text, sent_at, telegram_message_ids) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record["id"],
                record["digest_date"],
                record["item_count"],
                json.dumps(record["dimension_breakdown"]),
                json.dumps(record["change_type_distribution"]),
                json.dumps(record["high_importance_items"]),
                record.get("summary_en"),
                record.get("summary_zh"),
                record["message_text"],
                record["sent_at"],
                json.dumps(record["telegram_message_ids"]),
            ),
        )
    logger.info(
        "Digest persisted: date=%s items=%d", record["digest_date"], record["item_count"],
    )
