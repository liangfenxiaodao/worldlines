"""Read-only query functions for the web API."""

from __future__ import annotations

import json

from worldlines.web.deps import get_readonly_connection

# ---------------------------------------------------------------------------
# Allowed sort columns and ordering for list_items
# ---------------------------------------------------------------------------
_SORT_COLUMNS = {
    "analyzed_at": "a.analyzed_at",
    "importance": "CASE a.importance WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END",
    "timestamp": "i.timestamp",
}

_ALLOWED_ORDER = {"asc", "desc"}


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------
def get_stats(database_path: str) -> dict:
    """Return aggregate statistics across items, analyses, and digests."""
    with get_readonly_connection(database_path) as conn:
        total_items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        total_analyses = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        total_digests = conn.execute("SELECT COUNT(*) FROM digests").fetchone()[0]

        row = conn.execute(
            "SELECT digest_date FROM digests ORDER BY digest_date DESC LIMIT 1"
        ).fetchone()
        latest_digest_date = row[0] if row else None

        dimension_rows = conn.execute(
            "SELECT json_extract(value, '$.dimension') AS dim, COUNT(*) AS cnt "
            "FROM analyses, json_each(analyses.dimensions) "
            "GROUP BY dim"
        ).fetchall()
        dimension_breakdown = {r["dim"]: r["cnt"] for r in dimension_rows}

        change_type_rows = conn.execute(
            "SELECT change_type, COUNT(*) AS cnt FROM analyses GROUP BY change_type"
        ).fetchall()
        change_type_distribution = {r["change_type"]: r["cnt"] for r in change_type_rows}

        importance_rows = conn.execute(
            "SELECT importance, COUNT(*) AS cnt FROM analyses GROUP BY importance"
        ).fetchall()
        importance_distribution = {r["importance"]: r["cnt"] for r in importance_rows}

    return {
        "total_items": total_items,
        "total_analyses": total_analyses,
        "total_digests": total_digests,
        "latest_digest_date": latest_digest_date,
        "dimension_breakdown": dimension_breakdown,
        "change_type_distribution": change_type_distribution,
        "importance_distribution": importance_distribution,
    }


# ---------------------------------------------------------------------------
# list_digests
# ---------------------------------------------------------------------------
def list_digests(
    database_path: str, page: int = 1, per_page: int = 20
) -> tuple[list[dict], int]:
    """Return a paginated list of digests, newest first."""
    offset = (page - 1) * per_page

    with get_readonly_connection(database_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM digests").fetchone()[0]

        rows = conn.execute(
            "SELECT id, digest_date, item_count, dimension_breakdown, "
            "change_type_distribution, sent_at "
            "FROM digests ORDER BY digest_date DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()

    digests = []
    for r in rows:
        digests.append({
            "id": r["id"],
            "digest_date": r["digest_date"],
            "item_count": r["item_count"],
            "dimension_breakdown": json.loads(r["dimension_breakdown"]),
            "change_type_distribution": json.loads(r["change_type_distribution"]),
            "sent_at": r["sent_at"],
        })

    return digests, total


# ---------------------------------------------------------------------------
# get_digest_by_date
# ---------------------------------------------------------------------------
def get_digest_by_date(database_path: str, date: str) -> dict | None:
    """Return a single digest by its date string, or None."""
    with get_readonly_connection(database_path) as conn:
        row = conn.execute(
            "SELECT * FROM digests WHERE digest_date = ?", (date,)
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row["id"],
        "digest_date": row["digest_date"],
        "item_count": row["item_count"],
        "dimension_breakdown": json.loads(row["dimension_breakdown"]),
        "change_type_distribution": json.loads(row["change_type_distribution"]),
        "high_importance_items": json.loads(row["high_importance_items"]),
        "message_text": row["message_text"],
        "sent_at": row["sent_at"],
        "telegram_message_ids": json.loads(row["telegram_message_ids"]),
    }


# ---------------------------------------------------------------------------
# list_items
# ---------------------------------------------------------------------------
def list_items(
    database_path: str,
    *,
    filters: dict | None = None,
    page: int = 1,
    per_page: int = 20,
    sort: str = "analyzed_at",
    order: str = "desc",
) -> tuple[list[dict], int]:
    """Return a paginated, filtered, sorted list of items with their analyses."""
    filters = filters or {}
    offset = (page - 1) * per_page

    # Validate sort/order against whitelists
    if sort not in _SORT_COLUMNS:
        sort = "analyzed_at"
    if order not in _ALLOWED_ORDER:
        order = "desc"

    sort_expr = _SORT_COLUMNS[sort]

    # Build dynamic WHERE clauses
    conditions: list[str] = []
    params: list[object] = []

    if "dimension" in filters:
        conditions.append(
            "EXISTS (SELECT 1 FROM json_each(a.dimensions) "
            "WHERE json_extract(value, '$.dimension') = ?)"
        )
        params.append(filters["dimension"])

    if "change_type" in filters:
        conditions.append("a.change_type = ?")
        params.append(filters["change_type"])

    if "importance" in filters:
        conditions.append("a.importance = ?")
        params.append(filters["importance"])

    if "time_horizon" in filters:
        conditions.append("a.time_horizon = ?")
        params.append(filters["time_horizon"])

    if "source_type" in filters:
        conditions.append("i.source_type = ?")
        params.append(filters["source_type"])

    if "date_from" in filters:
        conditions.append("a.analyzed_at >= ?")
        params.append(filters["date_from"])

    if "date_to" in filters:
        conditions.append("a.analyzed_at < ?")
        params.append(filters["date_to"])

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    base_from = "FROM items i JOIN analyses a ON a.item_id = i.id"

    with get_readonly_connection(database_path) as conn:
        count_sql = f"SELECT COUNT(*) {base_from} {where_clause}"
        total = conn.execute(count_sql, params).fetchone()[0]

        # order is whitelisted above so safe to interpolate
        data_sql = (
            f"SELECT i.id, i.title, i.source_name, i.source_type, i.timestamp, "
            f"i.canonical_link, i.ingested_at, "
            f"a.id AS analysis_id, a.dimensions, a.change_type, a.time_horizon, "
            f"a.summary, a.importance, a.key_entities, a.analyzed_at, "
            f"a.analysis_version "
            f"{base_from} {where_clause} "
            f"ORDER BY {sort_expr} {order} "
            f"LIMIT ? OFFSET ?"
        )
        rows = conn.execute(data_sql, [*params, per_page, offset]).fetchall()

    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "title": r["title"],
            "source_name": r["source_name"],
            "source_type": r["source_type"],
            "timestamp": r["timestamp"],
            "canonical_link": r["canonical_link"],
            "ingested_at": r["ingested_at"],
            "analysis_id": r["analysis_id"],
            "dimensions": json.loads(r["dimensions"]),
            "change_type": r["change_type"],
            "time_horizon": r["time_horizon"],
            "summary": r["summary"],
            "importance": r["importance"],
            "key_entities": json.loads(r["key_entities"]),
            "analyzed_at": r["analyzed_at"],
            "analysis_version": r["analysis_version"],
        })

    return items, total


# ---------------------------------------------------------------------------
# get_item_by_id
# ---------------------------------------------------------------------------
def get_item_by_id(database_path: str, item_id: str) -> dict | None:
    """Return a single item with its analysis, or None."""
    with get_readonly_connection(database_path) as conn:
        row = conn.execute(
            "SELECT i.*, "
            "a.id AS analysis_id, a.dimensions, a.change_type, a.time_horizon, "
            "a.summary, a.importance, a.key_entities, a.analyzed_at, "
            "a.analysis_version "
            "FROM items i LEFT JOIN analyses a ON a.item_id = i.id "
            "WHERE i.id = ?",
            (item_id,),
        ).fetchone()

    if row is None:
        return None

    item = {
        "id": row["id"],
        "title": row["title"],
        "source_name": row["source_name"],
        "source_type": row["source_type"],
        "timestamp": row["timestamp"],
        "content": row["content"],
        "canonical_link": row["canonical_link"],
        "ingested_at": row["ingested_at"],
        "dedup_hash": row["dedup_hash"],
    }

    analysis = None
    if row["analysis_id"] is not None:
        analysis = {
            "id": row["analysis_id"],
            "dimensions": json.loads(row["dimensions"]),
            "change_type": row["change_type"],
            "time_horizon": row["time_horizon"],
            "summary": row["summary"],
            "importance": row["importance"],
            "key_entities": json.loads(row["key_entities"]),
            "analyzed_at": row["analyzed_at"],
            "analysis_version": row["analysis_version"],
        }

    return {"item": item, "analysis": analysis}
