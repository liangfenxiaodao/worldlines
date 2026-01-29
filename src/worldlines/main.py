"""Application entry point."""

from __future__ import annotations

import json
import logging
import signal
import sys

from worldlines.config import load_config

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


def _handle_signal(signum: int, _frame: object) -> None:
    sig_name = signal.Signals(signum).name
    logger.info("Received %s, shutting down", sig_name)
    sys.exit(0)


def main() -> None:
    """Load config, set up logging, and start the application."""
    config = load_config()

    _setup_logging(config.log_level, config.log_format)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info(
        "Worldlines starting (env=%s, db=%s, model=%s)",
        config.app_env,
        config.database_path,
        config.llm_model,
    )

    # TODO: Initialize database
    # TODO: Create scheduler
    # TODO: Register ingestion and digest jobs
    # TODO: Start scheduler

    logger.info("Startup complete — scheduler not yet implemented, exiting")


if __name__ == "__main__":
    main()
