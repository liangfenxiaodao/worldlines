"""Scheduled job functions — ingestion, analysis, digest."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from zoneinfo import ZoneInfo

from worldlines.analysis.classifier import classify_item
from worldlines.config import Config
from worldlines.digest.digest import generate_digest
from worldlines.ingestion.normalize import NormalizedItem, ingest_item
from worldlines.ingestion.rss_adapter import RSSAdapter
from worldlines.storage.connection import get_connection

logger = logging.getLogger(__name__)


def _record_run(
    database_path: str,
    run_type: str,
    started_at: str,
    result: dict,
    error: str | None = None,
) -> None:
    """Insert a pipeline run record into the pipeline_runs table."""
    finished_at = datetime.now(timezone.utc).isoformat()
    status = "error" if error else "success"
    with get_connection(database_path) as conn:
        conn.execute(
            "INSERT INTO pipeline_runs "
            "(id, run_type, started_at, finished_at, status, result, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                run_type,
                started_at,
                finished_at,
                status,
                json.dumps(result),
                error,
            ),
        )


def run_ingestion(config: Config) -> None:
    """Load sources config and ingest items from all enabled RSS adapters."""
    started_at = datetime.now(timezone.utc).isoformat()
    error_msg = None
    total_new = 0
    total_dup = 0

    try:
        with open(config.sources_config_path) as f:
            sources = json.load(f)

        for adapter_config in sources.get("adapters", []):
            if adapter_config.get("type") != "rss":
                continue
            if not adapter_config.get("enabled", True):
                continue

            adapter = RSSAdapter(config.database_path, config.max_items_per_source)
            adapter.configure(adapter_config)
            raw_items = adapter.fetch()

            for raw in raw_items:
                result = ingest_item(raw, config.database_path)
                if result.status == "new":
                    total_new += 1
                else:
                    total_dup += 1

        logger.info("Ingestion complete: %d new, %d duplicates", total_new, total_dup)
    except Exception:
        logger.exception("Ingestion failed")
        error_msg = "Ingestion failed (see logs)"

    _record_run(
        config.database_path, "ingestion", started_at,
        {"items_new": total_new, "items_duplicate": total_dup},
        error=error_msg,
    )


def run_analysis(config: Config) -> None:
    """Find unanalyzed items and classify each with the LLM."""
    started_at = datetime.now(timezone.utc).isoformat()
    error_msg = None
    items_found = 0
    analyzed = 0
    errors = 0

    try:
        with get_connection(config.database_path) as conn:
            rows = conn.execute(
                "SELECT i.id, i.title, i.source_name, i.source_type, "
                "i.timestamp, i.content, i.canonical_link, i.ingested_at, i.dedup_hash "
                "FROM items i "
                "LEFT JOIN analyses a ON i.id = a.item_id "
                "WHERE a.id IS NULL "
                "ORDER BY i.ingested_at ASC"
            ).fetchall()

        items_found = len(rows)

        if not rows:
            logger.info("Analysis: no unanalyzed items found")
        else:
            logger.info("Analysis: found %d unanalyzed items", len(rows))

            for row in rows:
                item = NormalizedItem(
                    id=row["id"],
                    title=row["title"],
                    source_name=row["source_name"],
                    source_type=row["source_type"],
                    timestamp=row["timestamp"],
                    content=row["content"],
                    canonical_link=row["canonical_link"],
                    ingested_at=row["ingested_at"],
                    dedup_hash=row["dedup_hash"],
                )
                try:
                    result = classify_item(
                        item,
                        api_key=config.llm_api_key,
                        model=config.llm_model,
                        analysis_version=config.analysis_version,
                        database_path=config.database_path,
                        temperature=config.llm_temperature,
                        max_retries=config.llm_max_retries,
                        timeout=config.llm_timeout_seconds,
                    )
                    if result.error:
                        errors += 1
                        logger.warning(
                            "Classification error for item %s: %s", item.id, result.error
                        )
                    else:
                        analyzed += 1
                except Exception:
                    errors += 1
                    logger.exception("Unexpected error classifying item %s", item.id)

            logger.info("Analysis complete: %d analyzed, %d errors", analyzed, errors)
    except Exception:
        logger.exception("Analysis failed")
        error_msg = "Analysis failed (see logs)"

    _record_run(
        config.database_path, "analysis", started_at,
        {"items_found": items_found, "items_analyzed": analyzed, "errors": errors},
        error=error_msg,
    )


def run_digest(config: Config) -> None:
    """Generate and deliver the daily digest."""
    started_at = datetime.now(timezone.utc).isoformat()
    error_msg = None
    run_result: dict = {}

    try:
        tz = ZoneInfo(config.digest_timezone)
        now = datetime.now(tz)
        digest_date = now.date().isoformat()
        local_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        local_next_midnight = local_midnight + timedelta(days=1)
        since = local_midnight.astimezone(timezone.utc).isoformat()
        until = local_next_midnight.astimezone(timezone.utc).isoformat()

        logger.info("Generating digest for %s (since %s, until %s)", digest_date, since, until)

        result = generate_digest(
            digest_date,
            since,
            until=until,
            database_path=config.database_path,
            bot_token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
            api_key=config.llm_api_key,
            model=config.llm_model,
            parse_mode=config.telegram_parse_mode,
            max_items=config.digest_max_items,
            max_retries=config.telegram_max_retries,
        )

        logger.info("Digest delivery: status=%s, error=%s", result.delivery_status, result.error)

        total_in_window = 0
        items_included = 0
        if result.digest_record:
            items_included = result.digest_record.get("item_count", 0)

        run_result = {
            "digest_date": digest_date,
            "since": since,
            "until": until,
            "total_in_window": total_in_window,
            "items_included": items_included,
            "delivery_status": result.delivery_status,
        }

        if result.error:
            error_msg = result.error
    except Exception:
        logger.exception("Digest failed")
        error_msg = "Digest failed (see logs)"

    _record_run(config.database_path, "digest", started_at, run_result, error=error_msg)


def run_pipeline(config: Config) -> None:
    """Run ingestion then analysis sequentially."""
    run_ingestion(config)
    run_analysis(config)
