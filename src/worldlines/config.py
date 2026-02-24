"""Configuration loading and validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    """Application configuration. All values sourced from environment variables."""

    # Required
    database_path: str
    llm_api_key: str
    llm_model: str
    telegram_bot_token: str
    telegram_chat_id: str

    # Optional — LLM
    llm_base_url: str = "https://api.anthropic.com"
    llm_max_retries: int = 3
    llm_timeout_seconds: int = 60
    llm_temperature: float = 0.0

    # Optional — Analysis
    analysis_version: str = "v1"
    exposure_mapping_version: str = "v1"
    exposure_max_per_run: int = 20
    cluster_synthesis_version: str = "v1"

    # Optional — Ingestion
    fetch_interval_minutes: int = 60
    max_items_per_source: int = 50
    sources_config_path: str = "./config/sources.json"

    # Optional — Digest
    digest_schedule_cron: str = "0 18 * * *"
    digest_timezone: str = "UTC"
    digest_max_items: int = 20
    telegram_parse_mode: str = "HTML"
    telegram_max_retries: int = 3

    # Optional — Backup
    backup_dir: str = "/data/backups"
    backup_retention_days: int = 7
    backup_schedule_cron: str = "0 3 * * *"

    # Optional — Application
    log_level: str = "INFO"
    log_format: str = "json"
    app_env: str = "production"


_REQUIRED_VARS = [
    "DATABASE_PATH",
    "LLM_API_KEY",
    "LLM_MODEL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
]


def load_config(env_path: str | Path | None = None) -> Config:
    """Load configuration from environment variables.

    Loads a .env file if present (for local development), then validates
    that all required variables are set. Raises ValueError listing any
    missing variables.
    """
    load_dotenv(dotenv_path=env_path)

    missing = [var for var in _REQUIRED_VARS if not os.environ.get(var)]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return Config(
        # Required
        database_path=os.environ["DATABASE_PATH"],
        llm_api_key=os.environ["LLM_API_KEY"],
        llm_model=os.environ["LLM_MODEL"],
        telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
        # Optional — LLM
        llm_base_url=os.environ.get("LLM_BASE_URL", "https://api.anthropic.com"),
        llm_max_retries=int(os.environ.get("LLM_MAX_RETRIES", "3")),
        llm_timeout_seconds=int(os.environ.get("LLM_TIMEOUT_SECONDS", "60")),
        llm_temperature=float(os.environ.get("LLM_TEMPERATURE", "0.0")),
        # Optional — Analysis
        analysis_version=os.environ.get("ANALYSIS_VERSION", "v1"),
        exposure_mapping_version=os.environ.get("EXPOSURE_MAPPING_VERSION", "v1"),
        exposure_max_per_run=int(os.environ.get("EXPOSURE_MAX_PER_RUN", "20")),
        cluster_synthesis_version=os.environ.get("CLUSTER_SYNTHESIS_VERSION", "v1"),
        # Optional — Ingestion
        fetch_interval_minutes=int(os.environ.get("FETCH_INTERVAL_MINUTES", "60")),
        max_items_per_source=int(os.environ.get("MAX_ITEMS_PER_SOURCE", "50")),
        sources_config_path=os.environ.get("SOURCES_CONFIG_PATH", "./config/sources.json"),
        # Optional — Digest
        digest_schedule_cron=os.environ.get("DIGEST_SCHEDULE_CRON", "0 18 * * *"),
        digest_timezone=os.environ.get("DIGEST_TIMEZONE", "UTC"),
        digest_max_items=int(os.environ.get("DIGEST_MAX_ITEMS", "20")),
        telegram_parse_mode=os.environ.get("TELEGRAM_PARSE_MODE", "HTML"),
        telegram_max_retries=int(os.environ.get("TELEGRAM_MAX_RETRIES", "3")),
        # Optional — Backup
        backup_dir=os.environ.get("BACKUP_DIR", "/data/backups"),
        backup_retention_days=int(os.environ.get("BACKUP_RETENTION_DAYS", "7")),
        backup_schedule_cron=os.environ.get("BACKUP_SCHEDULE_CRON", "0 3 * * *"),
        # Optional — Application
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        log_format=os.environ.get("LOG_FORMAT", "json"),
        app_env=os.environ.get("APP_ENV", "production"),
    )
