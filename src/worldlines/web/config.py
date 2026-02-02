"""Web-specific configuration loading and validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class WebConfig:
    """Web process configuration. Subset of worker config — no LLM or Telegram keys."""

    # Required
    database_path: str

    # Optional
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    static_dir: str = "./static"
    log_level: str = "INFO"


def load_web_config(env_path: str | Path | None = None) -> WebConfig:
    """Load web configuration from environment variables.

    Loads a .env file if present (for local development), then validates
    that DATABASE_PATH is set. Raises ValueError if missing.
    """
    load_dotenv(dotenv_path=env_path)

    if not os.environ.get("DATABASE_PATH"):
        raise ValueError("Missing required environment variable: DATABASE_PATH")

    return WebConfig(
        database_path=os.environ["DATABASE_PATH"],
        web_host=os.environ.get("WEB_HOST", "0.0.0.0"),
        web_port=int(os.environ.get("WEB_PORT", "8080")),
        static_dir=os.environ.get("STATIC_DIR", "./static"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
