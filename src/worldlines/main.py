"""Application entry point."""

from __future__ import annotations

import json
import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from worldlines.config import load_config
from worldlines.jobs import run_digest, run_pipeline
from worldlines.storage import init_db

logger = logging.getLogger("worldlines")


def _setup_logging(log_level: str, log_format: str) -> None:
    """Configure root logger based on config."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    if log_format == "json":
        formatter = logging.Formatter(
            json.dumps(
                {
                    "time": "%(asctime)s",
                    "level": "%(levelname)s",
                    "logger": "%(name)s",
                    "message": "%(message)s",
                }
            )
        )
    else:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)


def main() -> None:
    """Load config, set up logging, and start the application."""
    config = load_config()

    _setup_logging(config.log_level, config.log_format)

    logger.info(
        "Worldlines starting (env=%s, db=%s, model=%s)",
        config.app_env,
        config.database_path,
        config.llm_model,
    )

    init_db(config.database_path)

    scheduler = BlockingScheduler()

    def _handle_signal(signum: int, _frame: object) -> None:
        sig_name = signal.Signals(signum).name
        logger.info("Received %s, shutting down", sig_name)
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Run pipeline once at startup (non-fatal — scheduler must start regardless)
    logger.info("Running initial pipeline")
    try:
        run_pipeline(config)
    except Exception:
        logger.exception("Initial pipeline failed; scheduler will continue")

    # Schedule pipeline (ingestion + analysis) on interval
    scheduler.add_job(
        run_pipeline,
        trigger=IntervalTrigger(minutes=config.fetch_interval_minutes),
        args=[config],
        id="pipeline",
        name="Ingestion + Analysis pipeline",
    )

    # Schedule daily digest via cron
    cron_parts = config.digest_schedule_cron.split()
    scheduler.add_job(
        run_digest,
        trigger=CronTrigger(
            minute=cron_parts[0],
            hour=cron_parts[1],
            day=cron_parts[2],
            month=cron_parts[3],
            day_of_week=cron_parts[4],
            timezone=config.digest_timezone,
        ),
        args=[config],
        id="digest",
        name="Daily digest",
    )

    logger.info("Scheduler starting")
    scheduler.start()


if __name__ == "__main__":
    main()
