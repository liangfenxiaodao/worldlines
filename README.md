# Worldlines

Worldlines traces long-term structural change across compute, capital, energy, adoption, and governance.

It is not a news reader.
It is not a signal generator.
It is not designed to answer "what should I buy today?"

Instead, it answers:
- What long-term forces are strengthening or weakening?
- Where are real-world constraints emerging?
- How are capital, technology, and institutions adapting?

## Core Philosophy
The system avoids premature hypotheses.

Rather than starting with assumptions and looking for confirmation, it:
1. Observes changes across five structural dimensions
2. Accumulates signals over time
3. Allows patterns and hypotheses to emerge organically

## The Five Dimensions
All information is processed through these lenses:

1. Compute & Computational Paradigms
2. Capital Flows & Business Models
3. Energy, Resources & Physical Constraints
4. Technology Adoption & Industrial Diffusion
5. Governance, Regulation & Societal Response

A single event may touch multiple dimensions.

## What the System Produces
- Structured, neutral summaries of relevant information
- Classification by dimension, change type, and time horizon
- Periodic digests highlighting signal density and emerging patterns

## What the System Avoids
- Stock picking
- Price prediction
- Sensational or hype-driven narratives

## Intended Use
This system is intended to be used:
- Continuously
- Reflectively
- As a thinking aid, not a decision replacement

It is a tool for understanding, not forecasting.

## MVP

Ingest from RSS feeds, classify via LLM, deliver a daily Telegram digest — deployed to Fly.io and running unattended.

**Stack:** Python · SQLite · Fly.io · Anthropic Claude API

## Prerequisites

- Python 3.12 or later
- A [Fly.io](https://fly.io) account (for deployment)
- An Anthropic API key
- A Telegram bot token and chat ID

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/liangfenxiaodao/worldlines.git
cd worldlines
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the project in editable mode along with dev tools (pytest, ruff).

### 3. Configure environment variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
DATABASE_PATH=./worldlines.db
LLM_API_KEY=sk-...
LLM_MODEL=claude-sonnet-4-20250514
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=-1001234567890
```

The `.env` file is gitignored and must never be committed. See [Configuration](docs/configuration.md) for the full list of environment variables and their defaults.

## Running the Application

```bash
worldlines
```

This loads configuration from environment variables (or `.env`), initializes the SQLite database, and starts the application. The database file is created automatically at the path specified by `DATABASE_PATH`.

## Running Tests

```bash
pytest
```

Run with verbose output:

```bash
pytest -v
```

Run a specific test file:

```bash
pytest tests/test_storage.py -v
```

## Linting

```bash
ruff check src/ tests/
```

## Project Structure

```
worldlines/
├── src/worldlines/          # Application source code
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration loading and validation
│   ├── storage/             # SQLite storage layer
│   │   ├── connection.py    # Connection context manager
│   │   └── schema.py        # Schema DDL and initialization
│   ├── ingestion/           # Source adapters (RSS, etc.)
│   ├── analysis/            # LLM classification pipeline
│   └── digest/              # Telegram digest output
├── tests/                   # Test suite
├── config/                  # Runtime configuration files
│   └── sources.json         # RSS feed source definitions
├── docs/                    # Design documentation
├── pyproject.toml           # Project metadata and dependencies
├── Dockerfile               # Container build
├── fly.toml                 # Fly.io deployment config
└── .env.example             # Environment variable template
```

## Deployment (Fly.io)

### First-time setup

```bash
fly launch --no-deploy
fly volumes create worldlines_data --region sjc --size 1
```

### Set secrets

```bash
fly secrets set LLM_API_KEY=sk-...
fly secrets set LLM_MODEL=claude-sonnet-4-20250514
fly secrets set TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
fly secrets set TELEGRAM_CHAT_ID=-1001234567890
```

`DATABASE_PATH` and `SOURCES_CONFIG_PATH` are set in `fly.toml` and do not need to be configured separately.

### Deploy

```bash
fly deploy
```

## Documentation

| Document | Description |
|---|---|
| [System Design](docs/system-design.md) | High-level architecture, dimensions, lifecycle, deployment model |
| [Data Schemas](docs/schemas.md) | JSON schemas for all data structures |
| [Storage Design](docs/storage-design.md) | Storage architecture, temporal linking, re-analysis support |
| [API Contracts](docs/api-contracts.md) | Inter-component contracts and query interfaces |
| [AI Prompt Spec](docs/ai-prompt-spec.md) | Prompt templates, classification guidelines, validation rules |
| [Source Adapters](docs/source-adapters.md) | Adapter interface, RSS adapter spec, future adapters |
| [Configuration](docs/configuration.md) | All environment variables, defaults, and secrets management |
