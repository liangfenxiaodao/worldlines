"""Tests for worldlines.config."""

import os

import pytest

from worldlines.config import load_config

REQUIRED_ENV = {
    "DATABASE_PATH": "./test.db",
    "LLM_API_KEY": "sk-test-key",
    "LLM_MODEL": "claude-sonnet-4-20250514",
    "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF",
    "TELEGRAM_CHAT_ID": "-1001234567890",
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove all config-related env vars before each test."""
    for key in list(os.environ):
        if key in REQUIRED_ENV or key.startswith(("LLM_", "TELEGRAM_", "DIGEST_", "FETCH_")):
            monkeypatch.delenv(key, raising=False)
    for key in ("DATABASE_PATH", "ANALYSIS_VERSION", "MAX_ITEMS_PER_SOURCE",
                "SOURCES_CONFIG_PATH", "LOG_LEVEL", "LOG_FORMAT", "APP_ENV"):
        monkeypatch.delenv(key, raising=False)
    # Prevent .env file from re-setting variables during tests
    monkeypatch.setattr("worldlines.config.load_dotenv", lambda *a, **kw: None)


def test_missing_required_vars_raises(monkeypatch):
    """load_config raises ValueError listing all missing required variables."""
    with pytest.raises(ValueError, match="Missing required environment variables"):
        load_config()


def test_missing_subset_lists_all(monkeypatch):
    """Error message includes every missing variable name."""
    monkeypatch.setenv("DATABASE_PATH", "./test.db")
    with pytest.raises(ValueError, match="LLM_API_KEY") as exc_info:
        load_config()
    msg = str(exc_info.value)
    assert "LLM_MODEL" in msg
    assert "TELEGRAM_BOT_TOKEN" in msg
    assert "TELEGRAM_CHAT_ID" in msg


def test_load_config_with_required_vars(monkeypatch):
    """Config loads successfully when all required vars are set, with correct defaults."""
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    config = load_config()

    # Required values
    assert config.database_path == "./test.db"
    assert config.llm_api_key == "sk-test-key"
    assert config.llm_model == "claude-sonnet-4-20250514"
    assert config.telegram_bot_token == "123456:ABC-DEF"
    assert config.telegram_chat_id == "-1001234567890"

    # Defaults
    assert config.llm_base_url == "https://api.anthropic.com"
    assert config.llm_max_retries == 3
    assert config.llm_timeout_seconds == 60
    assert config.llm_temperature == 0.0
    assert config.analysis_version == "v1"
    assert config.fetch_interval_minutes == 60
    assert config.max_items_per_source == 50
    assert config.sources_config_path == "./config/sources.json"
    assert config.digest_schedule_cron == "0 18 * * *"
    assert config.digest_timezone == "UTC"
    assert config.digest_max_items == 20
    assert config.telegram_parse_mode == "HTML"
    assert config.telegram_max_retries == 3
    assert config.log_level == "INFO"
    assert config.log_format == "json"
    assert config.app_env == "production"


def test_config_is_frozen(monkeypatch):
    """Config is immutable after creation."""
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    config = load_config()

    with pytest.raises(AttributeError):
        config.database_path = "/other.db"
