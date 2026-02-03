"""Scheduled job functions — ingestion, analysis, digest."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from zoneinfo import ZoneInfo

from worldlines.analysis.classifier import classify_item
from worldlines.config import Config
from worldlines.digest.digest import generate_digest
from worldlines.ingestion.normalize import NormalizedItem, ingest_item
from worldlines.ingestion.rss_adapter import RSSAdapter
from worldlines.storage.connection import get_connection

logger = logging.getLogger(__name__)


def run_ingestion(config: Config) -> None:
    """Load sources config and ingest items from all enabled RSS adapters."""
    with open(config.sources_config_path) as f:
        sources = json.load(f)

    total_new = 0
    total_dup = 0

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


def run_analysis(config: Config) -> None:
    """Find unanalyzed items and classify each with the LLM."""
    with get_connection(config.database_path) as conn:
        rows = conn.execute(
            "SELECT i.id, i.title, i.source_name, i.source_type, "
            "i.timestamp, i.content, i.canonical_link, i.ingested_at, i.dedup_hash "
            "FROM items i "
            "LEFT JOIN analyses a ON i.id = a.item_id "
            "WHERE a.id IS NULL "
            "ORDER BY i.ingested_at ASC"
        ).fetchall()

    if not rows:
        logger.info("Analysis: no unanalyzed items found")
        return

    logger.info("Analysis: found %d unanalyzed items", len(rows))
    analyzed = 0
    errors = 0

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


def run_digest(config: Config) -> None:
    """Generate and deliver the daily digest."""
    tz = ZoneInfo(config.digest_timezone)
    now = datetime.now(tz)
    digest_date = now.date().isoformat()
    since = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    logger.info("Generating digest for %s (since %s)", digest_date, since)

    result = generate_digest(
        digest_date,
        since,
        database_path=config.database_path,
        bot_token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
        parse_mode=config.telegram_parse_mode,
        max_items=config.digest_max_items,
        max_retries=config.telegram_max_retries,
    )

    logger.info("Digest delivery: status=%s, error=%s", result.delivery_status, result.error)


def run_pipeline(config: Config) -> None:
    """Run ingestion then analysis sequentially."""
    run_ingestion(config)
    run_analysis(config)
