"""Scheduled job functions — ingestion, analysis, digest, backup."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zoneinfo import ZoneInfo

from worldlines.analysis.classifier import classify_item
from worldlines.config import Config
from worldlines.digest.digest import generate_digest
from worldlines.digest.telegram import send_message
import worldlines.ingestion  # noqa: F401  — triggers adapter registration
from worldlines.ingestion.normalize import NormalizedItem, ingest_item
from worldlines.ingestion.registry import get_adapter_class
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


def _send_alert(config: Config, message: str) -> None:
    """Send a Telegram alert for critical failures. Never raises."""
    try:
        text = f"[WORLDLINES ALERT]\n{message}"
        send_message(
            config.telegram_bot_token,
            config.telegram_chat_id,
            text,
            parse_mode="",
            max_retries=2,
        )
    except Exception:
        logger.exception("Failed to send alert")


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
            adapter_type = adapter_config.get("type", "")
            adapter_cls = get_adapter_class(adapter_type)
            if adapter_cls is None:
                logger.warning("Unknown adapter type '%s', skipping", adapter_type)
                continue
            if not adapter_config.get("enabled", True):
                continue

            adapter = adapter_cls(config.database_path, config.max_items_per_source)
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
        _send_alert(config, "Ingestion pipeline failed. Check logs for details.")

    _record_run(
        config.database_path, "ingestion", started_at,
        {"items_new": total_new, "items_duplicate": total_dup},
        error=error_msg,
    )


_MAX_CLASSIFICATION_ATTEMPTS = 3


def _record_analysis_error(database_path: str, item_id: str, error_msg: str) -> None:
    """Upsert an error record for a failed classification attempt."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection(database_path) as conn:
        conn.execute(
            "INSERT INTO analysis_errors (item_id, attempt_count, last_error, last_attempted_at) "
            "VALUES (?, 1, ?, ?) "
            "ON CONFLICT(item_id) DO UPDATE SET "
            "attempt_count = attempt_count + 1, last_error = ?, last_attempted_at = ?",
            (item_id, error_msg, now, error_msg, now),
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
                "LEFT JOIN analysis_errors ae ON i.id = ae.item_id "
                "WHERE a.id IS NULL "
                "AND (ae.attempt_count IS NULL OR ae.attempt_count < ?) "
                "ORDER BY i.ingested_at ASC",
                (_MAX_CLASSIFICATION_ATTEMPTS,),
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
                        _record_analysis_error(
                            config.database_path, item.id, result.error.get("message", "")
                        )
                        logger.warning(
                            "Classification error for item %s: %s", item.id, result.error
                        )
                    else:
                        analyzed += 1
                except Exception:
                    errors += 1
                    _record_analysis_error(config.database_path, item.id, "unexpected error")
                    logger.exception("Unexpected error classifying item %s", item.id)

            logger.info("Analysis complete: %d analyzed, %d errors", analyzed, errors)
    except Exception:
        logger.exception("Analysis failed")
        error_msg = "Analysis failed (see logs)"
        _send_alert(config, "Analysis pipeline failed. Check logs for details.")

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
            _send_alert(config, f"Digest delivery issue: {result.error}")
    except Exception:
        logger.exception("Digest failed")
        error_msg = "Digest failed (see logs)"
        _send_alert(config, "Digest pipeline failed. Check logs for details.")

    _record_run(config.database_path, "digest", started_at, run_result, error=error_msg)


def run_backup(config: Config) -> None:
    """Create a SQLite backup with retention policy."""
    started_at = datetime.now(timezone.utc).isoformat()
    error_msg = None
    backup_path = ""

    try:
        backup_dir = Path(config.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        backup_path = str(backup_dir / f"worldlines-{date_str}.db")

        # Use SQLite backup API for a safe, consistent copy
        source = sqlite3.connect(config.database_path)
        try:
            dest = sqlite3.connect(backup_path)
            try:
                source.backup(dest)
            finally:
                dest.close()
        finally:
            source.close()

        logger.info("Backup created: %s", backup_path)

        # Retention: delete backups older than N days
        cutoff = datetime.now(timezone.utc) - timedelta(days=config.backup_retention_days)
        removed = 0
        for f in sorted(backup_dir.glob("worldlines-*.db")):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    f.unlink()
                    removed += 1
            except OSError:
                logger.warning("Could not remove old backup: %s", f)
        if removed:
            logger.info("Removed %d old backup(s)", removed)

    except Exception:
        logger.exception("Backup failed")
        error_msg = "Backup failed (see logs)"
        _send_alert(config, "Database backup failed. Check logs for details.")

    _record_run(
        config.database_path, "backup", started_at,
        {"backup_path": backup_path},
        error=error_msg,
    )


def run_pipeline(config: Config) -> None:
    """Run ingestion then analysis sequentially."""
    run_ingestion(config)
    run_analysis(config)
