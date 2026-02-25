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
from worldlines.exposure.mapper import map_exposures
from worldlines.config import Config
from worldlines.digest.periodic import generate_periodic_summary
from worldlines.synthesis.synthesizer import synthesize_cluster
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
                result = ingest_item(
                    raw,
                    config.database_path,
                    similarity_threshold=config.similarity_dedup_threshold,
                    similarity_window_hours=config.similarity_dedup_window_hours,
                )
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
                        error_code = result.error.get("code", "")
                        # Only count item-specific errors toward the retry limit.
                        # Transient API errors (billing, rate limits, outages) should
                        # not permanently block items from being retried.
                        if error_code != "api_error":
                            _record_analysis_error(
                                config.database_path, item.id,
                                result.error.get("message", ""),
                            )
                        logger.warning(
                            "Classification error for item %s: %s", item.id, result.error
                        )
                        # Stop processing if the API is unavailable — remaining items
                        # will fail for the same reason.
                        if error_code == "api_error":
                            logger.warning("API error detected; stopping analysis early")
                            break
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


_MAX_EXPOSURE_ATTEMPTS = 3


def _record_exposure_error(database_path: str, analysis_id: str, error_msg: str) -> None:
    """Upsert an error record for a failed exposure mapping attempt."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection(database_path) as conn:
        conn.execute(
            "INSERT INTO exposure_errors (analysis_id, attempt_count, last_error, last_attempted_at) "
            "VALUES (?, 1, ?, ?) "
            "ON CONFLICT(analysis_id) DO UPDATE SET "
            "attempt_count = attempt_count + 1, last_error = ?, last_attempted_at = ?",
            (analysis_id, error_msg, now, error_msg, now),
        )


def run_exposure_mapping(config: Config) -> None:
    """Find eligible unmapped analyses and map exposures with the LLM."""
    started_at = datetime.now(timezone.utc).isoformat()
    error_msg = None
    analyses_found = 0
    mapped = 0
    skipped = 0
    errors = 0

    try:
        with get_connection(config.database_path) as conn:
            rows = conn.execute(
                "SELECT a.id AS analysis_id, a.dimensions, a.change_type, a.time_horizon, "
                "a.summary, a.importance, a.key_entities, "
                "i.title, i.source_name, i.source_type "
                "FROM analyses a "
                "JOIN items i ON a.item_id = i.id "
                "LEFT JOIN exposures e ON a.id = e.analysis_id "
                "LEFT JOIN exposure_errors ee ON a.id = ee.analysis_id "
                "WHERE a.eligible_for_exposure_mapping = 1 "
                "AND e.id IS NULL "
                "AND (ee.attempt_count IS NULL OR ee.attempt_count < ?) "
                "ORDER BY a.analyzed_at ASC "
                "LIMIT ?",
                (_MAX_EXPOSURE_ATTEMPTS, config.exposure_max_per_run),
            ).fetchall()

        analyses_found = len(rows)

        if not rows:
            logger.info("Exposure mapping: no eligible unmapped analyses found")
        else:
            logger.info("Exposure mapping: found %d eligible unmapped analyses", len(rows))

            for row in rows:
                analysis = {
                    "analysis_id": row["analysis_id"],
                    "dimensions": row["dimensions"],
                    "change_type": row["change_type"],
                    "time_horizon": row["time_horizon"],
                    "summary": row["summary"],
                    "importance": row["importance"],
                    "key_entities": row["key_entities"],
                }
                item = {
                    "title": row["title"],
                    "source_name": row["source_name"],
                    "source_type": row["source_type"],
                }
                try:
                    result = map_exposures(
                        analysis,
                        item,
                        api_key=config.llm_api_key,
                        model=config.llm_model,
                        exposure_mapping_version=config.exposure_mapping_version,
                        database_path=config.database_path,
                        temperature=config.llm_temperature,
                        max_retries=config.llm_max_retries,
                        timeout=config.llm_timeout_seconds,
                    )
                    if result.error:
                        errors += 1
                        error_code = result.error.get("code", "")
                        if error_code != "api_error":
                            _record_exposure_error(
                                config.database_path, row["analysis_id"],
                                result.error.get("message", ""),
                            )
                        logger.warning(
                            "Exposure mapping error for analysis %s: %s",
                            row["analysis_id"], result.error,
                        )
                        # Stop processing if the API is unavailable — remaining items
                        # will fail for the same reason.
                        if error_code == "api_error":
                            logger.warning("API error detected; stopping exposure mapping early")
                            break
                    elif result.skipped_reason:
                        skipped += 1
                    else:
                        mapped += 1
                except Exception:
                    errors += 1
                    _record_exposure_error(
                        config.database_path, row["analysis_id"], "unexpected error"
                    )
                    logger.exception(
                        "Unexpected error mapping analysis %s", row["analysis_id"]
                    )

            logger.info(
                "Exposure mapping complete: %d mapped, %d skipped, %d errors",
                mapped, skipped, errors,
            )
    except Exception:
        logger.exception("Exposure mapping failed")
        error_msg = "Exposure mapping failed (see logs)"
        _send_alert(config, "Exposure mapping pipeline failed. Check logs for details.")

    _record_run(
        config.database_path, "exposure", started_at,
        {"analyses_found": analyses_found, "mapped": mapped, "skipped": skipped, "errors": errors},
        error=error_msg,
    )


_TEMPORAL_LINK_WINDOW_DAYS = 90


def _determine_link_type(newer_change_type: str, older_change_type: str) -> str:
    """Determine the link type based on the change types of two linked items."""
    if newer_change_type == older_change_type:
        return "reinforces"
    if {newer_change_type, older_change_type} == {"reinforcing", "friction"}:
        return "contradicts"
    return "extends"


def run_temporal_linking(config: Config) -> None:
    """Link articles that share ticker symbols within the 90-day window."""
    started_at = datetime.now(timezone.utc).isoformat()
    error_msg = None
    links_created = 0
    pairs_considered = 0

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=_TEMPORAL_LINK_WINDOW_DAYS)).isoformat()
        now = datetime.now(timezone.utc).isoformat()

        with get_connection(config.database_path) as conn:
            rows = conn.execute(
                "SELECT i.id AS item_id, i.timestamp AS item_timestamp, a.change_type, "
                "json_extract(t.value, '$.ticker') AS ticker "
                "FROM items i "
                "JOIN analyses a ON a.item_id = i.id "
                "JOIN exposures e ON e.analysis_id = a.id "
                "JOIN json_each(e.exposures) t "
                "WHERE e.skipped_reason IS NULL "
                "AND json_extract(t.value, '$.ticker') IS NOT NULL "
                "AND i.timestamp >= ?",
                (cutoff,),
            ).fetchall()

        # Group by ticker -> list of {item_id, timestamp, change_type}
        ticker_items: dict[str, list[dict]] = {}
        for r in rows:
            ticker = r["ticker"]
            if ticker not in ticker_items:
                ticker_items[ticker] = []
            ticker_items[ticker].append({
                "item_id": r["item_id"],
                "timestamp": r["item_timestamp"],
                "change_type": r["change_type"],
            })

        # For each ticker with >=2 items, form ordered pairs (newer -> older)
        # Accumulate per unique (source_id, target_id): shared tickers and change_types
        pair_data: dict[tuple[str, str], dict] = {}
        for ticker, items in ticker_items.items():
            if len(items) < 2:
                continue
            # Sort descending by timestamp
            sorted_items = sorted(items, key=lambda x: x["timestamp"], reverse=True)
            for i, newer in enumerate(sorted_items):
                for older in sorted_items[i + 1:]:
                    key = (newer["item_id"], older["item_id"])
                    if key not in pair_data:
                        pair_data[key] = {
                            "tickers": [],
                            "newer_ct": newer["change_type"],
                            "older_ct": older["change_type"],
                        }
                    pair_data[key]["tickers"].append(ticker)

        pairs_considered = len(pair_data)

        with get_connection(config.database_path) as conn:
            for (source_id, target_id), data in pair_data.items():
                shared_tickers = data["tickers"]
                newer_ct = data["newer_ct"]
                older_ct = data["older_ct"]
                link_type = _determine_link_type(newer_ct, older_ct)
                rationale = f"Shared: {', '.join(sorted(shared_tickers))}. {newer_ct} \u2194 {older_ct}."
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO temporal_links "
                    "(id, source_item_id, target_item_id, link_type, created_at, rationale) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), source_id, target_id, link_type, now, rationale),
                )
                links_created += cursor.rowcount

        logger.info(
            "Temporal linking complete: %d links created, %d pairs considered",
            links_created, pairs_considered,
        )
    except Exception:
        logger.exception("Temporal linking failed")
        error_msg = "Temporal linking failed (see logs)"
        _send_alert(config, "Temporal linking pipeline failed. Check logs for details.")

    _record_run(
        config.database_path, "temporal_linking", started_at,
        {"links_created": links_created, "pairs_considered": pairs_considered},
        error=error_msg,
    )


def run_cluster_synthesis(config: Config) -> None:
    """Synthesize structural insights for each ticker cluster in the 90-day window."""
    started_at = datetime.now(timezone.utc).isoformat()
    error_msg = None
    tickers_found = 0
    synthesized = 0
    skipped = 0
    errors = 0

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=_TEMPORAL_LINK_WINDOW_DAYS)).isoformat()

        with get_connection(config.database_path) as conn:
            rows = conn.execute(
                "SELECT i.id AS item_id, "
                "json_extract(t.value, '$.ticker') AS ticker "
                "FROM items i "
                "JOIN analyses a ON a.item_id = i.id "
                "JOIN exposures e ON e.analysis_id = a.id "
                "JOIN json_each(e.exposures) t "
                "WHERE e.skipped_reason IS NULL "
                "AND json_extract(t.value, '$.ticker') IS NOT NULL "
                "AND i.timestamp >= ?",
                (cutoff,),
            ).fetchall()

        # Group by ticker -> sorted list of item_ids
        ticker_items: dict[str, list[str]] = {}
        for r in rows:
            ticker = r["ticker"]
            item_id = r["item_id"]
            if ticker not in ticker_items:
                ticker_items[ticker] = []
            if item_id not in ticker_items[ticker]:
                ticker_items[ticker].append(item_id)

        # Sort item_ids per ticker for stable comparison
        for ticker in ticker_items:
            ticker_items[ticker] = sorted(ticker_items[ticker])

        tickers_found = sum(1 for ids in ticker_items.values() if len(ids) >= 2)

        # Load existing syntheses for comparison
        with get_connection(config.database_path) as conn:
            existing_rows = conn.execute(
                "SELECT ticker, item_ids FROM cluster_syntheses"
            ).fetchall()
        existing: dict[str, str] = {r["ticker"]: r["item_ids"] for r in existing_rows}

        now = datetime.now(timezone.utc).isoformat()

        for ticker, item_ids in ticker_items.items():
            if len(item_ids) < 2:
                continue

            item_ids_json = json.dumps(item_ids)

            # Skip if cluster composition unchanged
            if existing.get(ticker) == item_ids_json:
                skipped += 1
                continue

            # Fetch full data for each item in the cluster
            placeholders = ",".join("?" * len(item_ids))
            with get_connection(config.database_path) as conn:
                item_rows = conn.execute(
                    f"SELECT i.id, i.title, i.source_name, i.timestamp, "  # noqa: S608
                    f"a.summary, a.change_type, a.time_horizon "
                    f"FROM items i JOIN analyses a ON a.item_id = i.id "
                    f"WHERE i.id IN ({placeholders}) "
                    f"ORDER BY i.timestamp DESC",
                    item_ids,
                ).fetchall()

            items_data = [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "source_name": r["source_name"],
                    "timestamp": r["timestamp"],
                    "summary": r["summary"],
                    "change_type": r["change_type"],
                    "time_horizon": r["time_horizon"],
                }
                for r in item_rows
            ]

            try:
                result = synthesize_cluster(
                    ticker,
                    items_data,
                    api_key=config.llm_api_key,
                    model=config.llm_model,
                    temperature=config.llm_temperature,
                    max_retries=config.llm_max_retries,
                    timeout=config.llm_timeout_seconds,
                )
            except Exception:
                errors += 1
                logger.exception("Unexpected error synthesizing cluster for ticker %s", ticker)
                continue

            if result.error:
                errors += 1
                logger.warning(
                    "Synthesis error for ticker %s: %s", ticker, result.error
                )
                if result.error.get("code") == "api_error":
                    logger.warning("API error detected; stopping cluster synthesis early")
                    break
                continue

            # UPSERT into cluster_syntheses
            with get_connection(config.database_path) as conn:
                conn.execute(
                    "INSERT INTO cluster_syntheses "
                    "(id, ticker, item_ids, item_count, synthesis, synthesized_at, synthesis_version) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(ticker) DO UPDATE SET "
                    "item_ids = excluded.item_ids, "
                    "item_count = excluded.item_count, "
                    "synthesis = excluded.synthesis, "
                    "synthesized_at = excluded.synthesized_at, "
                    "synthesis_version = excluded.synthesis_version",
                    (
                        str(uuid.uuid4()),
                        ticker,
                        item_ids_json,
                        len(item_ids),
                        result.synthesis,
                        now,
                        config.cluster_synthesis_version,
                    ),
                )
            synthesized += 1
            logger.info("Synthesized cluster for ticker %s (%d items)", ticker, len(item_ids))

        logger.info(
            "Cluster synthesis complete: %d tickers found, %d synthesized, %d skipped, %d errors",
            tickers_found, synthesized, skipped, errors,
        )
    except Exception:
        logger.exception("Cluster synthesis failed")
        error_msg = "Cluster synthesis failed (see logs)"
        _send_alert(config, "Cluster synthesis pipeline failed. Check logs for details.")

    _record_run(
        config.database_path, "cluster_synthesis", started_at,
        {"tickers_found": tickers_found, "synthesized": synthesized, "skipped": skipped, "errors": errors},
        error=error_msg,
    )


def run_periodic_summary(config: Config) -> None:
    """Generate and deliver a periodic structural summary over the configured window."""
    started_at = datetime.now(timezone.utc).isoformat()
    error_msg = None
    run_result: dict = {}

    try:
        window_days = config.periodic_summary_window_days
        now_utc = datetime.now(timezone.utc)
        # Align window to day boundaries
        until_dt = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        since_dt = until_dt - timedelta(days=window_days)
        since = since_dt.isoformat()
        until = until_dt.isoformat()
        # Idempotency key: end date + window size
        period_label = f"{until_dt.date().isoformat()}:{window_days}d"

        logger.info(
            "Generating periodic summary: period=%s, since=%s, until=%s",
            period_label, since, until,
        )

        result = generate_periodic_summary(
            period_label,
            window_days,
            since,
            until,
            database_path=config.database_path,
            bot_token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
            api_key=config.llm_api_key,
            model=config.llm_model,
            parse_mode=config.telegram_parse_mode,
            max_retries=config.telegram_max_retries,
        )

        logger.info(
            "Periodic summary: status=%s, error=%s",
            result.delivery_status, result.error,
        )

        run_result = {
            "period_label": period_label,
            "since": since,
            "until": until,
            "delivery_status": result.delivery_status,
        }

        if result.error:
            error_msg = result.error
            _send_alert(config, f"Periodic summary delivery issue: {result.error}")
    except Exception:
        logger.exception("Periodic summary failed")
        error_msg = "Periodic summary failed (see logs)"
        _send_alert(config, "Periodic summary pipeline failed. Check logs for details.")

    _record_run(
        config.database_path, "periodic_summary", started_at, run_result, error=error_msg,
    )


def run_pipeline(config: Config) -> None:
    """Run ingestion, analysis, exposure mapping, temporal linking, then cluster synthesis."""
    run_ingestion(config)
    run_analysis(config)
    run_exposure_mapping(config)
    run_temporal_linking(config)
    run_cluster_synthesis(config)
