# Worldlines — API Contracts

This document defines the contracts between Worldlines system components. Each contract specifies the input/output shapes and behavioral expectations for inter-component communication.

---

## 1. Overview

The system consists of four pipeline stages, each with a defined contract:

```
[Ingestion] → [Normalization & Dedup] → [AI Analysis] → [Exposure Mapping]
```

Additionally, there are query contracts for retrieving stored data.

---

## 2. Ingestion Contract

### 2.1 Purpose
Accepts raw information from heterogeneous sources and produces a uniform raw input record.

### 2.2 Input: Raw Source Item

```json
{
  "source_name": "string (required)",
  "source_type": "string (required) — enum: news | filing | report | research | government | industry | other",
  "title": "string (required)",
  "content": "string (required)",
  "url": "string | null",
  "published_at": "ISO 8601 datetime | null"
}
```

- `published_at` may be null if the source does not provide a publication date. The system will use ingestion time as a fallback.

### 2.3 Output: Normalization Request

```json
{
  "raw_item": { ... },
  "received_at": "ISO 8601 datetime"
}
```

### 2.4 Behavioral Expectations
- The ingestion layer does not filter, classify, or interpret content.
- All received items are forwarded for normalization.
- Source abstraction: the system treats all sources uniformly.

---

## 3. Normalization & Deduplication Contract

### 3.1 Purpose
Transforms raw input into a `NormalizedItem` and checks for duplicates.

### 3.2 Input
The output of the Ingestion stage (section 2.3).

### 3.3 Output: Normalization Result

```json
{
  "status": "string — enum: new | duplicate",
  "item": "NormalizedItem (as defined in schemas.md)",
  "duplicate_of": "uuid | null — present only if status is 'duplicate'"
}
```

### 3.4 Deduplication Logic
1. Compute `dedup_hash` from title + source name + content fingerprint
2. Check the Items Store for an existing item with the same hash
3. If match found:
   - Return `status: "duplicate"` with `duplicate_of` pointing to the existing item
   - Create a `DeduplicationRecord`
4. If no match:
   - Persist the `NormalizedItem` to the Items Store
   - Return `status: "new"` with the persisted item

### 3.5 Behavioral Expectations
- Near-duplicate detection (content similarity) is a future enhancement. Phase 1 uses exact hash matching only.
- Normalization must be idempotent: processing the same raw item twice produces the same `NormalizedItem` (modulo `ingested_at`).

---

## 4. AI Analysis Contract

### 4.1 Purpose
Classifies and summarizes a `NormalizedItem`, producing an `AnalyticalOutput`.

### 4.2 Input: Analysis Request

```json
{
  "item": "NormalizedItem",
  "analysis_version": "string — identifier for the current analytical framework"
}
```

### 4.3 Output: Analysis Response

```json
{
  "analysis": "AnalyticalOutput (as defined in schemas.md)",
  "eligible_for_exposure_mapping": "boolean"
}
```

- `eligible_for_exposure_mapping` is `true` when `importance` is `medium` or `high` and at least one dimension has `relevance: "primary"` with a concrete mechanism (supply chain, capacity, regulation, capex shift, adoption).

### 4.4 AI Behavioral Constraints
The AI layer must:
- Assign one or more dimensions with relevance levels
- Classify the change type
- Attribute a time horizon
- Produce a neutral, factual summary (max 500 characters)
- Assess structural importance
- Extract key entities

The AI layer must NOT:
- Make predictions
- Express opinions
- Label information as good or bad
- Recommend actions
- Use directional language (bullish, bearish, positive, negative)

### 4.5 Error Handling
If the AI layer cannot classify an item with sufficient confidence:

```json
{
  "analysis": null,
  "error": {
    "code": "classification_uncertain",
    "message": "string — explanation of why classification failed"
  }
}
```

Failed items are retained in the Items Store and may be re-submitted later.

---

## 5. Exposure Mapping Contract

### 5.1 Purpose
Maps an `AnalyticalOutput` to investable instruments, describing structural exposure.

### 5.2 Input: Mapping Request

```json
{
  "analysis": "AnalyticalOutput"
}
```

Only analyses where `eligible_for_exposure_mapping` is `true` should be submitted.

### 5.3 Output: Mapping Response

```json
{
  "exposure_record": "StructuralExposureRecord (as defined in schemas.md) | null",
  "skipped_reason": "string | null — present if no mapping was produced"
}
```

- `exposure_record` is `null` if no meaningful ticker mapping could be established.
- `skipped_reason` provides an explanation (e.g., "No identifiable publicly listed entities linked to the signal").

### 5.4 Mapping Behavioral Constraints
The mapping layer must:
- Identify listed companies structurally exposed to the described forces
- Classify each exposure using the taxonomy (type, role, strength, confidence)
- Provide a neutral rationale for each mapping
- Connect exposures to specific dimensions

The mapping layer must NOT:
- Label impacts as bullish or bearish
- Predict price movements
- Recommend buying, selling, or holding
- Infer portfolio actions

---

## 6. Query Contracts

### 6.1 Item Query

**Request:**
```json
{
  "filters": {
    "date_range": { "from": "ISO 8601", "to": "ISO 8601" },
    "source_type": "string | null",
    "text_search": "string | null"
  },
  "sort": { "field": "timestamp | ingested_at", "order": "asc | desc" },
  "pagination": { "offset": "integer", "limit": "integer (max 100)" }
}
```

**Response:**
```json
{
  "items": ["NormalizedItem[]"],
  "total_count": "integer",
  "has_more": "boolean"
}
```

### 6.2 Analysis Query

**Request:**
```json
{
  "filters": {
    "item_id": "uuid | null",
    "dimensions": ["string[] | null — filter to items matching any of these dimensions"],
    "change_type": "string | null",
    "time_horizon": "string | null",
    "importance": "string | null",
    "analysis_version": "string | null",
    "date_range": { "from": "ISO 8601", "to": "ISO 8601" }
  },
  "sort": { "field": "analyzed_at | importance", "order": "asc | desc" },
  "pagination": { "offset": "integer", "limit": "integer (max 100)" }
}
```

**Response:**
```json
{
  "analyses": ["AnalyticalOutput[]"],
  "total_count": "integer",
  "has_more": "boolean"
}
```

### 6.3 Exposure Query

**Request:**
```json
{
  "filters": {
    "ticker": "string | null",
    "exposure_type": "string | null",
    "exposure_strength": "string | null",
    "dimensions": ["string[] | null"],
    "date_range": { "from": "ISO 8601", "to": "ISO 8601" }
  },
  "sort": { "field": "mapped_at", "order": "asc | desc" },
  "pagination": { "offset": "integer", "limit": "integer (max 100)" }
}
```

**Response:**
```json
{
  "exposure_records": ["StructuralExposureRecord[]"],
  "total_count": "integer",
  "has_more": "boolean"
}
```

### 6.4 Temporal Links Query

**Request:**
```json
{
  "item_id": "uuid",
  "direction": "outgoing | incoming | both",
  "link_type": "string | null"
}
```

**Response:**
```json
{
  "links": [
    {
      "id": "uuid",
      "source_item_id": "uuid",
      "target_item_id": "uuid",
      "link_type": "string",
      "rationale": "string",
      "created_at": "ISO 8601"
    }
  ]
}
```

---

## 7. Cross-Cutting Concerns

### 7.1 Idempotency
- Ingestion and normalization are idempotent (dedup prevents double-processing)
- Analysis is not idempotent by design (re-analysis produces new records with new versions)
- Exposure mapping follows analysis: one mapping per analysis record

### 7.2 Error Propagation
Errors at any stage do not block the pipeline for other items. Each item is processed independently. Failed items are logged and available for retry.

### 7.3 Versioning
All contracts are versioned implicitly through `analysis_version`. When the analytical framework changes, the version identifier changes, and all new outputs are tagged accordingly.

### 7.4 Rate Limits
AI analysis and exposure mapping may be subject to external API rate limits. The system should implement backoff and queuing at these boundaries. Specific limits are implementation-dependent and will be defined during MVP development.
