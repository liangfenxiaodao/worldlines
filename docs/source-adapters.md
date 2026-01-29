# Worldlines — Source Adapter Specification

This document defines the source adapter interface, responsibilities, and the concrete adapters planned for the system.

---

## 1. Purpose

A **source adapter** is the boundary between the external world and the Worldlines ingestion pipeline. Each adapter knows how to fetch, parse, and emit raw items from a specific source type.

The rest of the system is source-agnostic. Once data passes through an adapter, its origin is captured in metadata but does not affect downstream processing.

---

## 2. Adapter Interface

Every source adapter must implement the following contract:

### 2.1 Interface Definition

```
SourceAdapter:
  name        → string           # Human-readable adapter name
  source_type → string           # One of the canonical source types (news, filing, report, etc.)
  fetch()     → RawSourceItem[]  # Fetch new items from the source
  configure(config) → void       # Accept adapter-specific configuration
```

### 2.2 Output: RawSourceItem

Each adapter emits items in the `RawSourceItem` format defined in `docs/api-contracts.md` section 2.2:

```json
{
  "source_name": "string",
  "source_type": "string",
  "title": "string",
  "content": "string",
  "url": "string | null",
  "published_at": "ISO 8601 datetime | null"
}
```

### 2.3 Behavioral Requirements

- **Idempotent fetching:** Adapters must track what has already been fetched (via timestamps, cursors, or seen-URL sets) to avoid emitting the same item repeatedly. The deduplication layer is a safety net, not a substitute for adapter-level tracking.
- **No filtering:** Adapters fetch and emit. They do not classify, rank, or discard items based on relevance. Relevance assessment happens downstream in the AI analysis layer.
- **No transformation beyond normalization:** Adapters parse source-specific formats into `RawSourceItem`. They do not summarize, translate, or enrich content.
- **Graceful failure:** If a source is unavailable, the adapter logs the failure and returns an empty result. It does not crash the pipeline or block other adapters.
- **Rate limit compliance:** Adapters must respect the source's rate limits and terms of service.

---

## 3. Adapter Lifecycle

```
[Scheduler triggers run]
       ↓
[Adapter.fetch()] → RawSourceItem[]
       ↓
[Ingestion pipeline receives items]
       ↓
[Normalization & Dedup]
       ↓
[Items Store]
```

Adapters are invoked by the scheduler. They do not run continuously. Each invocation fetches new items since the last run.

---

## 4. State Management

Each adapter needs to track its position to avoid re-fetching old items. Strategies by source type:

| Strategy | Description | Best for |
|---|---|---|
| Timestamp cursor | Store the timestamp of the most recent item fetched | APIs with reliable timestamps |
| URL/ID set | Store a set of already-seen item identifiers | RSS feeds, paginated APIs |
| Pagination cursor | Store an API-provided cursor or page token | APIs with cursor-based pagination |

Adapter state is persisted in the database (a simple key-value table or adapter-specific state record). It must survive restarts.

---

## 5. MVP Adapter: RSS/Atom Feed

The first adapter for MVP ingests items from RSS or Atom feeds.

### 5.1 Why RSS
- Widely available across news outlets, research publishers, and government agencies
- Structured format (title, link, description, date) maps cleanly to `RawSourceItem`
- No API keys required for most feeds
- Simple to implement

### 5.2 Configuration

```json
{
  "feeds": [
    {
      "url": "https://example.com/feed.xml",
      "source_name": "Example Publication",
      "source_type": "news"
    }
  ],
  "fetch_interval_minutes": 60,
  "max_items_per_feed": 50
}
```

- `feeds`: List of RSS/Atom feed URLs with metadata
- `fetch_interval_minutes`: How often the adapter runs (default: 60)
- `max_items_per_feed`: Maximum items to process per feed per run (prevents backfill floods)

### 5.3 Field Mapping

| RawSourceItem field | RSS/Atom source |
|---|---|
| `source_name` | From adapter config |
| `source_type` | From adapter config |
| `title` | `<title>` element |
| `content` | `<description>` or `<content:encoded>`, stripped of HTML |
| `url` | `<link>` element |
| `published_at` | `<pubDate>` or `<published>`, parsed to ISO 8601 |

### 5.4 State Tracking
The RSS adapter uses a combination of:
- Per-feed timestamp of most recent item seen
- Per-feed set of seen URLs (to handle feeds that don't update timestamps reliably)

### 5.5 Suggested Initial Feeds
Structural signals relevant to Worldlines' five dimensions can be sourced from:

- **Compute:** Semiconductor industry publications, cloud provider blogs
- **Capital:** Financial regulatory filings, major business press
- **Energy/Resources:** Energy agency publications, infrastructure trade press
- **Adoption:** Enterprise technology publications, industry analyst feeds
- **Governance:** Government gazette feeds, regulatory body announcements

Specific feed URLs will be configured at deployment time.

---

## 6. Future Adapters (Post-MVP)

### 6.1 SEC EDGAR Adapter
Ingests SEC filings (10-K, 10-Q, 8-K) for US-listed companies.
- Source type: `filing`
- Uses EDGAR full-text search API
- Filters to filings with structural relevance (capex disclosures, risk factors, material events)

### 6.2 Manual Input Adapter
Accepts items submitted directly by the user (via CLI, API, or Telegram reply).
- Source type: `other`
- No scheduling — items are pushed, not pulled
- Useful for capturing insights from sources without machine-readable feeds

### 6.3 API-Based News Adapter
Ingests from news APIs (e.g., NewsAPI, Mediastack) for broader coverage.
- Source type: `news`
- Requires API key (managed as a secret)
- Keyword/topic filtering at the API level to reduce noise

---

## 7. Adding a New Adapter

To add a new source adapter:

1. Implement the `SourceAdapter` interface (section 2.1)
2. Define the adapter's configuration schema
3. Implement state tracking appropriate to the source
4. Register the adapter with the scheduler
5. Add feed/source configuration to the deployment config
6. Test end-to-end: adapter → ingestion → normalization → dedup → Items Store
