"""Database schema definition and initialization."""

from __future__ import annotations

import logging
import sqlite3

from worldlines.storage.connection import get_connection

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """\
-- Normalized items ingested from sources
CREATE TABLE IF NOT EXISTS items (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    source_name     TEXT NOT NULL,
    source_type     TEXT NOT NULL CHECK (source_type IN (
                        'news', 'filing', 'transcript', 'report',
                        'research', 'government', 'policy', 'industry',
                        'other'
                    )),
    timestamp       TEXT NOT NULL,
    content         TEXT NOT NULL,
    canonical_link  TEXT,
    ingested_at     TEXT NOT NULL,
    dedup_hash      TEXT NOT NULL UNIQUE
);

-- AI analytical outputs
CREATE TABLE IF NOT EXISTS analyses (
    id                  TEXT PRIMARY KEY,
    item_id             TEXT NOT NULL REFERENCES items(id),
    dimensions          TEXT NOT NULL,          -- JSON array
    change_type         TEXT NOT NULL CHECK (change_type IN (
                            'reinforcing', 'friction', 'early_signal', 'neutral'
                        )),
    time_horizon        TEXT NOT NULL CHECK (time_horizon IN (
                            'short_term', 'medium_term', 'long_term'
                        )),
    summary             TEXT NOT NULL,
    importance          TEXT NOT NULL CHECK (importance IN (
                            'low', 'medium', 'high'
                        )),
    key_entities        TEXT NOT NULL,          -- JSON array
    analyzed_at         TEXT NOT NULL,
    analysis_version    TEXT NOT NULL
);

-- Structural exposure records mapping analyses to instruments
CREATE TABLE IF NOT EXISTS exposures (
    id              TEXT PRIMARY KEY,
    analysis_id     TEXT NOT NULL REFERENCES analyses(id),
    exposures       TEXT NOT NULL,              -- JSON array
    mapped_at       TEXT NOT NULL
);

-- Deduplication tracking
CREATE TABLE IF NOT EXISTS deduplication_records (
    canonical_item_id   TEXT NOT NULL REFERENCES items(id),
    duplicate_item_ids  TEXT NOT NULL,          -- JSON array
    deduped_at          TEXT NOT NULL,
    method              TEXT NOT NULL CHECK (method IN (
                            'hash_exact', 'content_similarity'
                        ))
);

-- Daily digest log
CREATE TABLE IF NOT EXISTS digests (
    id                          TEXT PRIMARY KEY,
    digest_date                 TEXT NOT NULL UNIQUE,
    item_count                  INTEGER NOT NULL,
    dimension_breakdown         TEXT NOT NULL,  -- JSON object
    change_type_distribution    TEXT NOT NULL,  -- JSON object
    high_importance_items       TEXT NOT NULL,  -- JSON array
    summary_en                  TEXT,           -- AI synthesis (nullable)
    summary_zh                  TEXT,           -- AI synthesis (nullable)
    message_text                TEXT NOT NULL,
    sent_at                     TEXT NOT NULL,
    telegram_message_ids        TEXT NOT NULL   -- JSON array
);

-- Adapter state for tracking fetch position
CREATE TABLE IF NOT EXISTS adapter_state (
    adapter_name    TEXT NOT NULL,
    feed_url        TEXT NOT NULL,
    state_data      TEXT NOT NULL,          -- JSON object
    updated_at      TEXT NOT NULL,
    PRIMARY KEY (adapter_name, feed_url)
);

-- Temporal links between items
CREATE TABLE IF NOT EXISTS temporal_links (
    id              TEXT PRIMARY KEY,
    source_item_id  TEXT NOT NULL REFERENCES items(id),
    target_item_id  TEXT NOT NULL REFERENCES items(id),
    link_type       TEXT NOT NULL CHECK (link_type IN (
                        'reinforces', 'contradicts', 'extends', 'supersedes'
                    )),
    created_at      TEXT NOT NULL,
    rationale       TEXT NOT NULL
);

-- Indexes: items
CREATE INDEX IF NOT EXISTS idx_items_timestamp ON items(timestamp);
CREATE INDEX IF NOT EXISTS idx_items_source_type ON items(source_type);
CREATE INDEX IF NOT EXISTS idx_items_ingested_at ON items(ingested_at);

-- Indexes: analyses
CREATE INDEX IF NOT EXISTS idx_analyses_item_id ON analyses(item_id);
CREATE INDEX IF NOT EXISTS idx_analyses_change_type ON analyses(change_type);
CREATE INDEX IF NOT EXISTS idx_analyses_importance ON analyses(importance);
CREATE INDEX IF NOT EXISTS idx_analyses_analyzed_at ON analyses(analyzed_at);
CREATE INDEX IF NOT EXISTS idx_analyses_analysis_version ON analyses(analysis_version);

-- Indexes: exposures
CREATE INDEX IF NOT EXISTS idx_exposures_analysis_id ON exposures(analysis_id);

-- Indexes: deduplication_records
CREATE INDEX IF NOT EXISTS idx_dedup_canonical_item_id ON deduplication_records(canonical_item_id);

-- Indexes: digests
CREATE INDEX IF NOT EXISTS idx_digests_sent_at ON digests(sent_at);

-- Indexes: temporal_links
CREATE INDEX IF NOT EXISTS idx_temporal_links_source_item_id ON temporal_links(source_item_id);
CREATE INDEX IF NOT EXISTS idx_temporal_links_target_item_id ON temporal_links(target_item_id);
CREATE INDEX IF NOT EXISTS idx_temporal_links_link_type ON temporal_links(link_type);
"""


def _migrate_digests_summary(conn: sqlite3.Connection) -> None:
    """Add summary_en and summary_zh columns to existing digests table."""
    for col in ("summary_en", "summary_zh"):
        try:
            conn.execute(f"ALTER TABLE digests ADD COLUMN {col} TEXT")  # noqa: S608
        except sqlite3.OperationalError:
            pass  # Column already exists


def init_db(database_path: str) -> None:
    """Create all tables and indexes if they do not already exist."""
    with get_connection(database_path) as conn:
        conn.executescript(_SCHEMA_SQL)
        _migrate_digests_summary(conn)
    logger.info("Database initialized at %s", database_path)
