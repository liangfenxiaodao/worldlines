# Worldlines — Web Frontend Design

This document defines the technical design for the Worldlines web frontend: a read-only web interface for browsing historical digests and classified items.

---

## 1. Overview

The web frontend adds a browser-based interface to Worldlines. It provides:

- A dashboard with system statistics
- Browsable, paginated daily digests
- Filterable item list with full analysis details

The frontend is a **read-only** view over the existing SQLite database. It does not modify data or interfere with the existing worker process.

---

## 2. Architecture

Two processes run in the same Fly.io app, sharing a single persistent volume:

```
┌─────────────────────────────────────────────────┐
│                   Fly.io App                     │
│                                                  │
│  ┌──────────────┐       ┌──────────────────┐    │
│  │    worker     │       │       web        │    │
│  │  (scheduler)  │       │ (FastAPI + SPA)  │    │
│  │              │       │                  │    │
│  │  worldlines   │       │  worldlines-web  │    │
│  └──────┬───────┘       └────────┬─────────┘    │
│         │                        │               │
│         └────────┬───────────────┘               │
│                  │                                │
│          ┌───────▼───────┐                       │
│          │  /data/        │                       │
│          │  worldlines.db │                       │
│          └───────────────┘                       │
│           (persistent volume)                    │
└─────────────────────────────────────────────────┘
```

### Concurrency model

SQLite is configured with WAL (Write-Ahead Logging) mode. The worker process is the sole writer. The web process opens read-only connections (`?mode=ro` URI or `PRAGMA query_only=ON`). WAL mode allows concurrent readers alongside a single writer without blocking.

### Process separation

| Process | Command | Role |
|---------|---------|------|
| `worker` | `worldlines` | Existing scheduler: ingestion, analysis, digest delivery |
| `web` | `worldlines-web` | FastAPI server: API + static SPA files |

Both processes are defined in `fly.toml` and share the same Docker image.

---

## 3. API Backend

### 3.1 Framework

**FastAPI** with:
- Pydantic v2 response models
- `sqlite3` for database access (read-only connections)
- Uvicorn as the ASGI server
- Static file mounting for the built SPA

### 3.2 Entry point

A new console script `worldlines-web` defined in `pyproject.toml`:

```python
# src/worldlines/web/main.py

def main() -> None:
    config = load_config()
    uvicorn.run(
        "worldlines.web.app:app",
        host="0.0.0.0",
        port=8080,
        log_level=config.log_level.lower(),
    )
```

### 3.3 Application factory

```python
# src/worldlines/web/app.py

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Worldlines", docs_url="/api/docs")

# API routes
app.include_router(api_router, prefix="/api/v1")

# SPA static files (must be last — catches all non-API routes)
app.mount("/", StaticFiles(directory="static", html=True), name="spa")
```

### 3.4 Database access

A read-only connection dependency:

```python
# src/worldlines/web/deps.py

from contextlib import contextmanager

@contextmanager
def get_readonly_connection(database_path: str):
    conn = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA query_only=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
```

### 3.5 Endpoints

#### `GET /api/v1/stats`

Dashboard overview statistics.

**Response:**
```json
{
  "total_items": 1234,
  "total_analyses": 1180,
  "total_digests": 45,
  "latest_digest_date": "2025-06-15",
  "dimension_breakdown": {
    "compute_and_computational_paradigms": 312,
    "capital_flows_and_business_models": 287,
    "energy_resources_and_physical_constraints": 198,
    "technology_adoption_and_industrial_diffusion": 245,
    "governance_regulation_and_societal_response": 138
  },
  "change_type_distribution": {
    "reinforcing": 420,
    "friction": 310,
    "early_signal": 280,
    "neutral": 170
  },
  "importance_distribution": {
    "high": 95,
    "medium": 485,
    "low": 600
  }
}
```

**SQL (summary):**
```sql
SELECT COUNT(*) FROM items;
SELECT COUNT(*) FROM analyses;
SELECT COUNT(*) FROM digests;
SELECT digest_date FROM digests ORDER BY digest_date DESC LIMIT 1;
-- Dimension breakdown: parse JSON dimensions column and count
-- Change type / importance: GROUP BY on analyses table
```

#### `GET /api/v1/digests`

List digests, paginated.

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number (1-indexed) |
| `per_page` | int | 20 | Items per page (max 100) |

**Response:**
```json
{
  "digests": [
    {
      "id": "uuid",
      "digest_date": "2025-06-15",
      "item_count": 12,
      "dimension_breakdown": { ... },
      "change_type_distribution": { ... },
      "sent_at": "2025-06-15T18:00:00Z"
    }
  ],
  "total": 45,
  "page": 1,
  "per_page": 20,
  "pages": 3
}
```

**SQL:**
```sql
SELECT id, digest_date, item_count, dimension_breakdown,
       change_type_distribution, sent_at
FROM digests
ORDER BY digest_date DESC
LIMIT ? OFFSET ?;
```

#### `GET /api/v1/digests/{date}`

Single digest by date (YYYY-MM-DD).

**Response:**
```json
{
  "id": "uuid",
  "digest_date": "2025-06-15",
  "item_count": 12,
  "dimension_breakdown": { ... },
  "change_type_distribution": { ... },
  "high_importance_items": [ ... ],
  "message_text": "<b>Worldlines Daily Digest...</b>",
  "sent_at": "2025-06-15T18:00:00Z"
}
```

**SQL:**
```sql
SELECT * FROM digests WHERE digest_date = ?;
```

#### `GET /api/v1/items`

List items with their analyses, filterable and paginated.

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `per_page` | int | 20 | Items per page (max 100) |
| `dimension` | str | null | Filter by dimension (substring match on JSON) |
| `change_type` | str | null | Filter: reinforcing, friction, early_signal, neutral |
| `importance` | str | null | Filter: low, medium, high |
| `time_horizon` | str | null | Filter: short_term, medium_term, long_term |
| `source_type` | str | null | Filter by source type |
| `date_from` | str | null | Start date (ISO 8601, filters on analyzed_at) |
| `date_to` | str | null | End date (ISO 8601, filters on analyzed_at) |
| `sort` | str | "analyzed_at" | Sort field: analyzed_at, importance, timestamp |
| `order` | str | "desc" | Sort order: asc, desc |

**Response:**
```json
{
  "items": [
    {
      "item_id": "uuid",
      "analysis_id": "uuid",
      "title": "TSMC reports record Q2 revenue",
      "source_name": "Semiconductor Engineering",
      "source_type": "industry",
      "timestamp": "2025-06-14T10:30:00Z",
      "canonical_link": "https://...",
      "summary": "TSMC's Q2 revenue reached...",
      "dimensions": [
        { "dimension": "compute_and_computational_paradigms", "relevance": "primary" }
      ],
      "change_type": "reinforcing",
      "time_horizon": "medium_term",
      "importance": "high",
      "analyzed_at": "2025-06-14T12:00:00Z"
    }
  ],
  "total": 1180,
  "page": 1,
  "per_page": 20,
  "pages": 59
}
```

**SQL (base):**
```sql
SELECT i.id AS item_id, a.id AS analysis_id,
       i.title, i.source_name, i.source_type,
       i.timestamp, i.canonical_link,
       a.summary, a.dimensions, a.change_type,
       a.time_horizon, a.importance, a.analyzed_at
FROM items i
JOIN analyses a ON a.item_id = i.id
WHERE 1=1
  -- dynamic filters appended here
ORDER BY a.analyzed_at DESC
LIMIT ? OFFSET ?;
```

Dimension filtering uses `json_each()` on the dimensions column:

```sql
AND EXISTS (
  SELECT 1 FROM json_each(a.dimensions)
  WHERE json_extract(value, '$.dimension') = ?
)
```

#### `GET /api/v1/items/{id}`

Single item with full content and analysis.

**Response:**
```json
{
  "item": {
    "id": "uuid",
    "title": "TSMC reports record Q2 revenue",
    "source_name": "Semiconductor Engineering",
    "source_type": "industry",
    "timestamp": "2025-06-14T10:30:00Z",
    "content": "Full article content...",
    "canonical_link": "https://...",
    "ingested_at": "2025-06-14T11:00:00Z"
  },
  "analysis": {
    "id": "uuid",
    "dimensions": [ ... ],
    "change_type": "reinforcing",
    "time_horizon": "medium_term",
    "summary": "...",
    "importance": "high",
    "key_entities": ["TSMC", "semiconductor", "advanced packaging"],
    "analyzed_at": "2025-06-14T12:00:00Z",
    "analysis_version": "v1"
  }
}
```

**SQL:**
```sql
SELECT i.*, a.id AS analysis_id, a.dimensions, a.change_type,
       a.time_horizon, a.summary, a.importance,
       a.key_entities, a.analyzed_at, a.analysis_version
FROM items i
LEFT JOIN analyses a ON a.item_id = i.id
WHERE i.id = ?;
```

### 3.6 Pydantic models

```python
# src/worldlines/web/models.py

class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int

class StatsResponse(BaseModel):
    total_items: int
    total_analyses: int
    total_digests: int
    latest_digest_date: str | None
    dimension_breakdown: dict[str, int]
    change_type_distribution: dict[str, int]
    importance_distribution: dict[str, int]

class DigestSummary(BaseModel):
    id: str
    digest_date: str
    item_count: int
    dimension_breakdown: dict[str, int]
    change_type_distribution: dict[str, int]
    sent_at: str

class DigestDetail(DigestSummary):
    high_importance_items: list[dict]
    message_text: str

class DigestListResponse(BaseModel):
    digests: list[DigestSummary]
    total: int
    page: int
    per_page: int
    pages: int

class ItemSummary(BaseModel):
    item_id: str
    analysis_id: str
    title: str
    source_name: str
    source_type: str
    timestamp: str
    canonical_link: str | None
    summary: str
    dimensions: list[dict]
    change_type: str
    time_horizon: str
    importance: str
    analyzed_at: str

class ItemListResponse(BaseModel):
    items: list[ItemSummary]
    total: int
    page: int
    per_page: int
    pages: int

class ItemDetail(BaseModel):
    id: str
    title: str
    source_name: str
    source_type: str
    timestamp: str
    content: str
    canonical_link: str | None
    ingested_at: str

class AnalysisDetail(BaseModel):
    id: str
    dimensions: list[dict]
    change_type: str
    time_horizon: str
    summary: str
    importance: str
    key_entities: list[str]
    analyzed_at: str
    analysis_version: str

class ItemDetailResponse(BaseModel):
    item: ItemDetail
    analysis: AnalysisDetail | None
```

### 3.7 Query module

Database queries are encapsulated in a standalone module, separate from the API routes:

```python
# src/worldlines/web/queries.py

def get_stats(database_path: str) -> dict: ...
def list_digests(database_path: str, page: int, per_page: int) -> tuple[list[dict], int]: ...
def get_digest_by_date(database_path: str, date: str) -> dict | None: ...
def list_items(database_path: str, *, filters: dict, page: int, per_page: int, sort: str, order: str) -> tuple[list[dict], int]: ...
def get_item_by_id(database_path: str, item_id: str) -> dict | None: ...
```

This module uses `get_readonly_connection()` and returns plain dicts. It has no dependency on FastAPI.

---

## 4. Frontend

### 4.1 Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Framework | React 18 | Widely supported, large ecosystem |
| Build tool | Vite | Fast builds, good TypeScript support |
| Language | TypeScript | Type safety for API responses |
| Routing | React Router v6 | Standard SPA routing |
| HTTP client | fetch (native) | No additional dependency needed |
| Styling | CSS Modules or Tailwind CSS | Scoped styles, minimal footprint |

### 4.2 Project structure

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   └── client.ts          # API fetch functions
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── DigestList.tsx
│   │   ├── DigestDetail.tsx
│   │   ├── ItemList.tsx
│   │   └── ItemDetail.tsx
│   ├── components/
│   │   ├── Layout.tsx          # Shell with nav
│   │   ├── Pagination.tsx
│   │   ├── FilterBar.tsx
│   │   ├── DimensionBadge.tsx
│   │   ├── ImportanceBadge.tsx
│   │   └── ChangeTypeBadge.tsx
│   └── types/
│       └── api.ts              # TypeScript types matching Pydantic models
└── public/
    └── favicon.ico
```

### 4.3 Pages

#### Dashboard (`/`)

- Fetches `GET /api/v1/stats`
- Displays: total items, total analyses, total digests, latest digest date
- Bar or summary cards for dimension breakdown and change type distribution
- Link to latest digest and to full digest list

#### Digest list (`/digests`)

- Fetches `GET /api/v1/digests?page=N`
- Paginated cards showing: date, item count, dimension breakdown summary
- Click navigates to `/digests/:date`

#### Digest detail (`/digests/:date`)

- Fetches `GET /api/v1/digests/{date}`
- Renders the digest `message_text` (HTML content from Telegram format)
- Shows metadata: item count, dimension breakdown, change type distribution
- Links to individual items via `high_importance_items`

#### Item list (`/items`)

- Fetches `GET /api/v1/items?page=N&dimension=...&change_type=...`
- Filter bar with dropdowns: dimension, change type, importance, time horizon, date range
- Paginated table/cards showing: title, source, summary snippet, badges for dimension/change_type/importance
- Click navigates to `/items/:id`

#### Item detail (`/items/:id`)

- Fetches `GET /api/v1/items/{id}`
- Full item content (rendered text)
- Complete analysis: dimensions with relevance, change type, time horizon, summary, importance, key entities
- Link to canonical source URL

### 4.4 API client

```typescript
// frontend/src/api/client.ts

const BASE = "/api/v1";

export async function fetchStats(): Promise<StatsResponse> {
  const res = await fetch(`${BASE}/stats`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchDigests(page: number): Promise<DigestListResponse> { ... }
export async function fetchDigest(date: string): Promise<DigestDetail> { ... }
export async function fetchItems(params: ItemFilters): Promise<ItemListResponse> { ... }
export async function fetchItem(id: string): Promise<ItemDetailResponse> { ... }
```

### 4.5 Build output

Vite builds to `frontend/dist/`. The Dockerfile copies this to `/app/static/` in the container. FastAPI serves it as static files with `html=True` for SPA fallback routing.

**Vite config:**
```typescript
// frontend/vite.config.ts
export default defineConfig({
  build: { outDir: "dist" },
  server: {
    proxy: { "/api": "http://localhost:8080" }  // dev proxy
  }
});
```

---

## 5. Deployment

### 5.1 Dockerfile changes

Add a Node.js build stage for the frontend:

```dockerfile
# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Build Python
FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# Stage 3: Final image
FROM python:3.12-slim

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/worldlines /usr/local/bin/worldlines
COPY --from=builder /usr/local/bin/worldlines-web /usr/local/bin/worldlines-web
COPY src/ /app/src/
COPY config/ /app/config/
COPY --from=frontend-builder /build/dist /app/static/

RUN mkdir -p /data && \
    useradd --system --no-create-home appuser && \
    chown appuser:appuser /data

USER appuser
WORKDIR /app

CMD ["worldlines"]
```

### 5.2 fly.toml changes

```toml
app = "worldlines"
primary_region = "sjc"

[env]
  DATABASE_PATH = "/data/worldlines.db"
  SOURCES_CONFIG_PATH = "/app/config/sources.json"
  LLM_MODEL = "claude-3-haiku-20240307"
  ANALYSIS_VERSION = "v1"

[mounts]
  source = "worldlines_data"
  destination = "/data"

[processes]
  worker = "worldlines"
  web    = "worldlines-web"

[[services]]
  internal_port = 8080
  protocol = "tcp"
  processes = ["web"]

  [[services.ports]]
    port = 80
    handlers = ["http"]

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [services.concurrency]
    type = "connections"
    hard_limit = 25
    soft_limit = 20

[[vm]]
  size = "shared-cpu-1x"
  memory = "256mb"
```

Key changes:
- `[processes]` splits `app` into `worker` and `web`
- `[[services]]` routes HTTP traffic to the `web` process on port 8080
- Worker process has no exposed ports (same as current behavior)
- Both processes share the same volume mount

### 5.3 pyproject.toml changes

Add FastAPI and Uvicorn as dependencies, and the new console script:

```toml
dependencies = [
    "anthropic",
    "httpx",
    "feedparser",
    "python-dotenv",
    "apscheduler>=3.10,<4",
    "fastapi>=0.110,<1",
    "uvicorn[standard]>=0.29,<1",
]

[project.scripts]
worldlines = "worldlines.main:main"
worldlines-web = "worldlines.web.main:main"
```

### 5.4 New file layout

```
src/worldlines/
├── web/
│   ├── __init__.py
│   ├── main.py          # Uvicorn entry point
│   ├── app.py           # FastAPI application factory
│   ├── config.py        # Web-specific config (port, static dir)
│   ├── deps.py          # Read-only DB connection dependency
│   ├── models.py        # Pydantic response models
│   ├── queries.py       # SQL query functions
│   └── routes.py        # API route handlers
frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── src/
│   └── ...              # React application
└── public/
    └── ...
```

---

## 6. Configuration

The web process reuses the existing `Config` dataclass for `DATABASE_PATH`. Additional web-specific settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_PORT` | 8080 | Port for the web server |
| `WEB_HOST` | 0.0.0.0 | Bind address |
| `STATIC_DIR` | ./static | Path to built SPA files |

These are optional and have sensible defaults for Fly.io deployment. No new secrets are required.

---

## 7. Security

- **Read-only database access**: The web process opens SQLite in read-only mode. No mutations are possible.
- **No authentication (MVP)**: The web interface is public. Authentication can be added later via Fly.io Machines HTTP auth or a middleware layer.
- **CORS**: Not needed when SPA and API are served from the same origin.
- **Input validation**: All query parameters are validated by FastAPI/Pydantic. SQL queries use parameterized statements.
- **No sensitive data**: The database contains publicly sourced information. No PII, credentials, or proprietary data.

---

## 8. Performance

- **SQLite WAL mode**: Concurrent readers do not block the writer. The web process reading while the worker writes is safe.
- **Pagination**: All list endpoints are paginated with configurable limits (max 100 per page).
- **JSON parsing**: Dimension filtering uses SQLite's `json_each()` function, which has adequate performance for the expected data volume (thousands of items, not millions).
- **Static files**: Vite produces optimized, minified, code-split bundles. FastAPI serves them with appropriate caching headers.

---

## 9. Testing

### API tests

Integration tests using FastAPI's `TestClient` with a pre-seeded SQLite database:

```python
# tests/test_web_api.py

from fastapi.testclient import TestClient

def test_stats_returns_counts(seeded_db):
    client = TestClient(create_app(seeded_db))
    response = client.get("/api/v1/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_items" in data

def test_items_filter_by_dimension(seeded_db):
    client = TestClient(create_app(seeded_db))
    response = client.get("/api/v1/items?dimension=compute_and_computational_paradigms")
    assert response.status_code == 200
    ...
```

### Query module tests

Unit tests for `queries.py` that verify SQL correctness against a test database:

```python
def test_list_items_with_filters(seeded_db):
    items, total = list_items(seeded_db, filters={"change_type": "reinforcing"}, ...)
    assert all(item["change_type"] == "reinforcing" for item in items)
```

### Frontend tests

Deferred to post-MVP. Basic smoke tests can be added with Vitest if needed.

---

## 10. Implementation phases

### Phase 1: API backend
1. Add `src/worldlines/web/queries.py` — read-only query functions and `deps.py` — connection helper
2. Add `src/worldlines/web/app.py`, `routes.py`, `models.py` — FastAPI application with all endpoints
3. Add `tests/test_web_api.py` — integration tests

### Phase 2: Frontend
4. Initialize `frontend/` with Vite + React + TypeScript
5. Implement dashboard, digest list, digest detail pages
6. Implement item list with filtering and item detail pages

### Phase 3: Deployment
7. Update `Dockerfile` for multi-stage build (Node.js + Python)
8. Update `fly.toml` for dual-process deployment; update `pyproject.toml` with new dependencies and script
