# Worldlines — Configuration Reference

This document lists all configuration variables for the Worldlines system. All values are injected via environment variables. No configuration should be hardcoded in source code or container images.

---

## 1. Configuration Loading

Configuration is loaded from environment variables at startup. A `.env` file may be used for local development but must never be committed to the repository.

A `.env.example` file in the repository root documents all variables without sensitive values.

---

## 2. Required Variables (MVP)

These must be set for the system to function.

### 2.1 Database

| Variable | Description | Example |
|---|---|---|
| `DATABASE_PATH` | Path to the SQLite database file | `/data/worldlines.db` |

### 2.2 LLM / AI Layer

| Variable | Description | Example |
|---|---|---|
| `LLM_API_KEY` | API key for the LLM provider | `sk-...` |
| `LLM_MODEL` | Model identifier to use for classification | `claude-sonnet-4-20250514` |
| `LLM_BASE_URL` | Base URL for the LLM API (if not using default) | `https://api.anthropic.com` |

### 2.3 Telegram

| Variable | Description | Example |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | `123456:ABC-DEF...` |
| `TELEGRAM_CHAT_ID` | Target chat/channel/group ID for digests | `-1001234567890` |

---

## 3. Optional Variables

These have sensible defaults and can be overridden as needed.

### 3.1 Analysis

| Variable | Default | Description |
|---|---|---|
| `ANALYSIS_VERSION` | `v1` | Version identifier for the current analytical framework. Change when prompt logic changes materially. |
| `LLM_MAX_RETRIES` | `3` | Maximum retry attempts for LLM API calls |
| `LLM_TIMEOUT_SECONDS` | `60` | Timeout per LLM API call |
| `LLM_TEMPERATURE` | `0.0` | Temperature for classification (0.0 for deterministic output) |

### 3.2 Ingestion

| Variable | Default | Description |
|---|---|---|
| `FETCH_INTERVAL_MINUTES` | `60` | How often source adapters run |
| `MAX_ITEMS_PER_SOURCE` | `50` | Maximum items to process per source per run |

### 3.3 Telegram Digest

| Variable | Default | Description |
|---|---|---|
| `DIGEST_SCHEDULE_CRON` | `0 18 * * *` | Cron expression for daily digest (default: 6 PM UTC) |
| `DIGEST_TIMEZONE` | `UTC` | Timezone for digest scheduling and date display |
| `DIGEST_MAX_ITEMS` | `20` | Maximum number of items to include in a single digest |
| `TELEGRAM_PARSE_MODE` | `HTML` | Telegram message format (`HTML` or `MarkdownV2`) |
| `TELEGRAM_MAX_RETRIES` | `3` | Maximum retry attempts for Telegram API calls |

### 3.4 Application

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | `json` | Log output format: `json` (structured) or `text` (human-readable) |
| `APP_ENV` | `production` | Environment identifier: `development`, `staging`, `production` |

---

## 4. Source Adapter Configuration

Source adapters are configured via a JSON configuration file or environment variable.

| Variable | Default | Description |
|---|---|---|
| `SOURCES_CONFIG_PATH` | `./config/sources.json` | Path to the source adapter configuration file |

### 4.1 Source Configuration File Format

```json
{
  "adapters": [
    {
      "type": "rss",
      "enabled": true,
      "feeds": [
        {
          "url": "https://example.com/feed.xml",
          "source_name": "Example Publication",
          "source_type": "news"
        }
      ]
    }
  ]
}
```

See `docs/source-adapters.md` for full adapter configuration details.

---

## 5. Secrets Management

### 5.1 What Counts as a Secret
The following variables contain sensitive values and must be managed through the cloud provider's secret manager:

- `DATABASE_PATH` (not a secret per se, but platform-specific)
- `LLM_API_KEY`
- `TELEGRAM_BOT_TOKEN`

### 5.2 Local Development
For local development, use a `.env` file:

```
# .env (DO NOT COMMIT)
DATABASE_PATH=./worldlines.db
LLM_API_KEY=sk-...
LLM_MODEL=claude-sonnet-4-20250514
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=-1001234567890
```

### 5.3 Production (Fly.io)
In production, secrets are set via the Fly.io CLI:

```
fly secrets set LLM_API_KEY=sk-...
fly secrets set TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
fly secrets set TELEGRAM_CHAT_ID=-1001234567890
```

`DATABASE_PATH` is set in `fly.toml` to point to the persistent volume (e.g., `/data/worldlines.db`).

---

## 6. `.env.example`

The repository should include this file at the root:

```
# Database (SQLite file path)
DATABASE_PATH=./worldlines.db

# LLM
LLM_API_KEY=
LLM_MODEL=claude-sonnet-4-20250514
LLM_BASE_URL=https://api.anthropic.com
LLM_MAX_RETRIES=3
LLM_TIMEOUT_SECONDS=60
LLM_TEMPERATURE=0.0

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_PARSE_MODE=HTML
TELEGRAM_MAX_RETRIES=3

# Analysis
ANALYSIS_VERSION=v1

# Ingestion
FETCH_INTERVAL_MINUTES=60
MAX_ITEMS_PER_SOURCE=50
SOURCES_CONFIG_PATH=./config/sources.json

# Digest
DIGEST_SCHEDULE_CRON=0 18 * * *
DIGEST_TIMEZONE=UTC
DIGEST_MAX_ITEMS=20

# Application
LOG_LEVEL=INFO
LOG_FORMAT=json
APP_ENV=production
```
