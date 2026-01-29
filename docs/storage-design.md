# Worldlines — Storage Design

This document specifies the storage architecture for the Worldlines system. It covers the separation of raw and analytical data, temporal linking, and support for re-analysis.

---

## 1. Design Principles

### 1.1 Separation of Raw Data and Analysis
Raw ingested items and their analytical outputs are stored in **separate logical stores**. This separation:

- Allows re-analysis of historical items with updated frameworks without altering source data
- Keeps the ingestion pipeline independent of the analysis pipeline
- Enables versioned analytical outputs to coexist

### 1.2 Append-Only Analytical History
Analytical outputs are never overwritten. When an item is re-analyzed, a new `AnalyticalOutput` record is created with an updated `analysis_version`. This preserves the full history of how the system's understanding has evolved.

### 1.3 Temporal Integrity
All records carry timestamps. The system distinguishes between:

- **Event time** (`timestamp` on NormalizedItem): when the underlying event occurred
- **Ingestion time** (`ingested_at` on NormalizedItem): when the system first received the item
- **Analysis time** (`analyzed_at` on AnalyticalOutput): when the analysis was produced
- **Mapping time** (`mapped_at` on StructuralExposureRecord): when the exposure mapping was created

---

## 2. Logical Data Stores

### 2.1 Items Store
Contains all `NormalizedItem` records.

**Purpose:** Single source of truth for all ingested information.

**Key access patterns:**
- Insert new items during ingestion
- Lookup by `id`
- Lookup by `dedup_hash` for deduplication
- Query by `timestamp` range for temporal analysis
- Query by `source.type` for source-level filtering

**Retention:** Indefinite. All items are retained to support longitudinal analysis.

### 2.2 Analysis Store
Contains all `AnalyticalOutput` records.

**Purpose:** Stores every classification and summary produced by the AI layer.

**Key access patterns:**
- Insert new analysis results
- Query by `item_id` to retrieve all analyses for a given item
- Query by `dimensions` to find items within a structural dimension
- Query by `change_type` to filter by structural change pattern
- Query by `importance` to surface high-relevance items
- Query by `time_horizon` for horizon-based filtering
- Query by `analyzed_at` range for temporal slicing of analysis history
- Query by `analysis_version` to isolate outputs from a specific framework version

### 2.3 Exposure Store
Contains all `StructuralExposureRecord` records.

**Purpose:** Maps analytical signals to investable instruments.

**Key access patterns:**
- Insert new exposure mappings
- Query by `analysis_id` to retrieve exposures for a given analysis
- Query by `ticker` to find all signals relevant to a specific instrument
- Query by `exposure_type` or `exposure_strength` for filtered views
- Query by `dimensions_implicated` for dimension-level exposure aggregation

### 2.4 Deduplication Store
Contains all `DeduplicationRecord` records.

**Purpose:** Preserves lineage of merged items.

**Key access patterns:**
- Insert when deduplication occurs
- Lookup by `duplicate_item_ids` to trace a removed item to its canonical version

---

## 3. Temporal Linking

### 3.1 Purpose
Signals about the same structural force may arrive across days, weeks, or months. Temporal linking connects related items across time, enabling the system to surface accumulation patterns.

### 3.2 Link Structure

```json
{
  "id": "uuid",
  "source_item_id": "uuid",
  "target_item_id": "uuid",
  "link_type": "reinforces | contradicts | extends | supersedes",
  "created_at": "ISO 8601 datetime",
  "rationale": "Brief explanation of the relationship (max 200 chars)"
}
```

### 3.3 Link Types

| Type | Meaning |
|---|---|
| `reinforces` | The target item strengthens the signal from the source item |
| `contradicts` | The target item presents evidence counter to the source item |
| `extends` | The target item adds new information to the same structural trajectory |
| `supersedes` | The target item renders the source item obsolete or outdated |

### 3.4 Link Generation
Temporal links may be generated:

- **Automatically** during analysis, when the AI layer identifies connections to previously analyzed items
- **Manually** by the user during review

Links are stored separately from items and analyses, maintaining the separation principle.

---

## 4. Re-analysis Support

### 4.1 Motivation
As the analytical framework evolves (new prompt strategies, refined dimension definitions, updated classification criteria), historical items may need to be re-analyzed.

### 4.2 Mechanism
1. A new `analysis_version` identifier is assigned to the updated framework
2. Selected items are passed through the updated analysis pipeline
3. New `AnalyticalOutput` records are created with the new version
4. Previous analyses remain intact and queryable
5. If exposure mapping criteria change, new `StructuralExposureRecord` entries may be created

### 4.3 Selecting Items for Re-analysis
Re-analysis is triggered selectively, not globally. Candidate selection strategies:

- **By dimension:** Re-analyze all items in a dimension whose definition has changed
- **By date range:** Re-analyze items from a specific period
- **By importance:** Prioritize re-analysis of high-importance items
- **By staleness:** Re-analyze items whose most recent analysis is older than a threshold

---

## 5. Data Lifecycle

```
Source → Ingest → Normalize → Deduplicate → Store (Items Store)
                                                ↓
                                          Analyze (AI Layer)
                                                ↓
                                          Store (Analysis Store)
                                                ↓
                                    [if importance ≥ medium]
                                                ↓
                                          Map Exposure
                                                ↓
                                          Store (Exposure Store)
```

At each stage, the system only moves forward. No stage mutates data produced by a prior stage.

---

## 6. Technology Considerations

This document intentionally does not prescribe a specific database technology. The storage design is compatible with:

- **Relational databases** (PostgreSQL, SQLite) for structured queries and ACID guarantees
- **Document stores** (MongoDB) for flexible schema evolution
- **Hybrid approaches** using relational storage for items/analyses and a search engine for full-text queries

Technology selection will be made during MVP implementation based on scale requirements, deployment constraints, and operational complexity preferences.

### 6.1 Minimum Requirements
Any chosen storage solution must support:

- UUID-based primary keys
- Timestamp-based range queries
- Array field querying (for dimensions, key_entities)
- Transactional writes (at minimum, per-record atomicity)
- Data export for backup and migration
