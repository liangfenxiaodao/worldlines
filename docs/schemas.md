# Worldlines — Data Schemas

This document defines the canonical data structures used throughout the Worldlines system. All schemas are presented in JSON Schema (draft 2020-12) notation with accompanying explanations.

---

## 1. Normalized Item

A **Normalized Item** is the canonical internal representation of any ingested information, regardless of source. Every piece of incoming data is transformed into this shape before any analysis occurs.

### Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "NormalizedItem",
  "type": "object",
  "required": ["id", "title", "source", "timestamp", "content", "canonical_link", "ingested_at"],
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique identifier for the normalized item."
    },
    "title": {
      "type": "string",
      "minLength": 1,
      "description": "A concise title describing the item."
    },
    "source": {
      "type": "object",
      "required": ["name", "type"],
      "properties": {
        "name": {
          "type": "string",
          "description": "Human-readable source name (e.g., 'Financial Times', 'SEC Filing')."
        },
        "type": {
          "type": "string",
          "enum": ["news", "filing", "report", "research", "government", "industry", "other"],
          "description": "Category of origin."
        }
      },
      "description": "Origin metadata."
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "Publication or event timestamp (ISO 8601)."
    },
    "content": {
      "type": "string",
      "description": "Full text content of the item."
    },
    "canonical_link": {
      "type": ["string", "null"],
      "format": "uri",
      "description": "Canonical URL for the item. Null if no URL exists."
    },
    "ingested_at": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp when the item was ingested into the system (ISO 8601)."
    },
    "dedup_hash": {
      "type": "string",
      "description": "Hash used for deduplication. Generated from title + source + content fingerprint."
    }
  }
}
```

### Notes

- `source.type` is intentionally coarse. The system does not privilege any single channel.
- `dedup_hash` supports the deduplication step described in system design section 5.3.
- `canonical_link` is nullable because some sources (e.g., internal reports) may not have URLs.

---

## 2. Analytical Output

An **Analytical Output** is the result of AI-assisted classification and summarization applied to a Normalized Item. It captures dimension assignment, change type, time horizon, summary, and importance.

### Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AnalyticalOutput",
  "type": "object",
  "required": ["id", "item_id", "dimensions", "change_type", "time_horizon", "summary", "importance", "analyzed_at"],
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique identifier for this analysis."
    },
    "item_id": {
      "type": "string",
      "format": "uuid",
      "description": "Reference to the NormalizedItem that was analyzed."
    },
    "dimensions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["dimension", "relevance"],
        "properties": {
          "dimension": {
            "type": "string",
            "enum": [
              "compute_and_computational_paradigms",
              "capital_flows_and_business_models",
              "energy_resources_and_physical_constraints",
              "technology_adoption_and_industrial_diffusion",
              "governance_regulation_and_societal_response"
            ],
            "description": "One of the five structural dimensions."
          },
          "relevance": {
            "type": "string",
            "enum": ["primary", "secondary"],
            "description": "Whether the item is centrally about this dimension or tangentially related."
          }
        }
      },
      "minItems": 1,
      "description": "Dimensions this item maps to. An item may map to multiple dimensions."
    },
    "change_type": {
      "type": "string",
      "enum": ["reinforcing", "friction", "early_signal", "neutral"],
      "description": "The type of structural change this item represents."
    },
    "time_horizon": {
      "type": "string",
      "enum": ["short_term", "medium_term", "long_term"],
      "description": "Likely time horizon of the structural force described."
    },
    "summary": {
      "type": "string",
      "maxLength": 500,
      "description": "Neutral, factual summary. Non-evaluative. No predictions or recommendations."
    },
    "importance": {
      "type": "string",
      "enum": ["low", "medium", "high"],
      "description": "Structural relevance, not urgency. Reflects how much this item contributes to understanding long-term trajectories."
    },
    "key_entities": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Key companies, technologies, institutions, or regions mentioned."
    },
    "analyzed_at": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp when the analysis was produced (ISO 8601)."
    },
    "analysis_version": {
      "type": "string",
      "description": "Version identifier for the analytical framework used. Supports re-analysis as frameworks evolve."
    }
  }
}
```

### Notes

- `dimensions` is an array because items frequently span multiple dimensions (system design 7.1).
- `change_type` values map directly to the classification in system design 7.2.
- `summary` is capped at 500 characters to enforce brevity and non-editorializing.
- `analysis_version` enables re-analysis (system design 9.4) by tracking which framework produced each output.
- AI must not produce predictions, opinions, or directional labels in any field.

---

## 3. Structural Exposure Record

A **Structural Exposure Record** maps an Analytical Output to one or more investable instruments (tickers), describing exposure without directionality.

### Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "StructuralExposureRecord",
  "type": "object",
  "required": ["id", "analysis_id", "exposures", "mapped_at"],
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique identifier for this exposure record."
    },
    "analysis_id": {
      "type": "string",
      "format": "uuid",
      "description": "Reference to the AnalyticalOutput that triggered this mapping."
    },
    "exposures": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["ticker", "exposure_type", "business_role", "exposure_strength", "confidence", "rationale"],
        "properties": {
          "ticker": {
            "type": "string",
            "description": "Exchange-listed ticker symbol (e.g., 'AAPL', 'TSMC')."
          },
          "exposure_type": {
            "type": "string",
            "enum": ["direct", "indirect", "contextual"],
            "description": "Direct: primary actor. Indirect: upstream/downstream. Contextual: peer benchmark only."
          },
          "business_role": {
            "type": "string",
            "enum": [
              "infrastructure_operator",
              "upstream_supplier",
              "downstream_adopter",
              "platform_intermediary",
              "regulated_entity",
              "capital_allocator",
              "other"
            ],
            "description": "The company's role relative to the structural signal."
          },
          "exposure_strength": {
            "type": "string",
            "enum": ["core", "material", "peripheral"],
            "description": "Core: central to revenue/cost. Material: meaningful but not dominant. Peripheral: weak linkage."
          },
          "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "Based on source quality and clarity of mechanism."
          },
          "dimensions_implicated": {
            "type": "array",
            "items": {
              "type": "string",
              "enum": [
                "compute_and_computational_paradigms",
                "capital_flows_and_business_models",
                "energy_resources_and_physical_constraints",
                "technology_adoption_and_industrial_diffusion",
                "governance_regulation_and_societal_response"
              ]
            },
            "description": "Which structural dimensions link this ticker to the signal."
          },
          "rationale": {
            "type": "string",
            "maxLength": 300,
            "description": "Brief neutral explanation of why this ticker is linked. No directional claims."
          }
        }
      },
      "minItems": 1,
      "description": "List of tickers exposed to the structural signal."
    },
    "mapped_at": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp when the mapping was produced (ISO 8601)."
    }
  }
}
```

### Notes

- Exposure mapping is only applied when the underlying analysis has `importance` of `medium` or `high` (system design 8.3).
- `rationale` must never contain directional language (bullish, bearish, buy, sell).
- `business_role` uses a fixed enum with an `other` escape hatch for roles not yet categorized.
- `dimensions_implicated` connects exposure back to the structural dimensions for traceability.

---

## 4. Deduplication Record

A **Deduplication Record** tracks when items are merged during the deduplication step.

### Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "DeduplicationRecord",
  "type": "object",
  "required": ["canonical_item_id", "duplicate_item_ids", "deduped_at"],
  "properties": {
    "canonical_item_id": {
      "type": "string",
      "format": "uuid",
      "description": "The surviving item ID after deduplication."
    },
    "duplicate_item_ids": {
      "type": "array",
      "items": {
        "type": "string",
        "format": "uuid"
      },
      "minItems": 1,
      "description": "Item IDs that were identified as duplicates and merged into the canonical item."
    },
    "deduped_at": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp of the deduplication event."
    },
    "method": {
      "type": "string",
      "enum": ["hash_exact", "content_similarity"],
      "description": "Deduplication method used."
    }
  }
}
```

---

## 5. Daily Digest Record

A **Daily Digest Record** captures the content of a Telegram daily digest sent to the user. It serves as a log of what was communicated and supports historical review.

### Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "DailyDigestRecord",
  "type": "object",
  "required": ["id", "digest_date", "item_count", "dimension_breakdown", "high_importance_items", "change_type_distribution", "sent_at"],
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique identifier for this digest."
    },
    "digest_date": {
      "type": "string",
      "format": "date",
      "description": "The date this digest covers (YYYY-MM-DD)."
    },
    "item_count": {
      "type": "integer",
      "minimum": 0,
      "description": "Total number of items ingested and analyzed for this digest period."
    },
    "dimension_breakdown": {
      "type": "object",
      "properties": {
        "compute_and_computational_paradigms": { "type": "integer" },
        "capital_flows_and_business_models": { "type": "integer" },
        "energy_resources_and_physical_constraints": { "type": "integer" },
        "technology_adoption_and_industrial_diffusion": { "type": "integer" },
        "governance_regulation_and_societal_response": { "type": "integer" }
      },
      "description": "Count of items per structural dimension (items may span multiple dimensions)."
    },
    "change_type_distribution": {
      "type": "object",
      "properties": {
        "reinforcing": { "type": "integer" },
        "friction": { "type": "integer" },
        "early_signal": { "type": "integer" },
        "neutral": { "type": "integer" }
      },
      "description": "Count of items per change type."
    },
    "high_importance_items": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["item_id", "analysis_id", "title", "summary", "dimensions", "change_type"],
        "properties": {
          "item_id": { "type": "string", "format": "uuid" },
          "analysis_id": { "type": "string", "format": "uuid" },
          "title": { "type": "string" },
          "summary": { "type": "string" },
          "dimensions": {
            "type": "array",
            "items": { "type": "string" }
          },
          "change_type": { "type": "string" }
        }
      },
      "description": "Items with importance medium or high, included with their summaries."
    },
    "message_text": {
      "type": "string",
      "description": "The rendered message text as sent to Telegram."
    },
    "sent_at": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp when the digest was sent (ISO 8601)."
    },
    "telegram_message_ids": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Telegram message IDs returned after sending. Supports multi-message digests."
    }
  }
}
```

### Notes

- `high_importance_items` includes items with `importance` of `medium` or `high` to surface the most structurally relevant signals.
- `message_text` preserves exactly what was sent, enabling review without re-rendering.
- `telegram_message_ids` is an array because long digests may be split across multiple Telegram messages.

---

## 6. Enumeration Reference

For clarity, the canonical enum values used across all schemas:

| Field | Values |
|---|---|
| `source.type` | `news`, `filing`, `report`, `research`, `government`, `industry`, `other` |
| `dimension` | `compute_and_computational_paradigms`, `capital_flows_and_business_models`, `energy_resources_and_physical_constraints`, `technology_adoption_and_industrial_diffusion`, `governance_regulation_and_societal_response` |
| `change_type` | `reinforcing`, `friction`, `early_signal`, `neutral` |
| `time_horizon` | `short_term`, `medium_term`, `long_term` |
| `importance` | `low`, `medium`, `high` |
| `exposure_type` | `direct`, `indirect`, `contextual` |
| `business_role` | `infrastructure_operator`, `upstream_supplier`, `downstream_adopter`, `platform_intermediary`, `regulated_entity`, `capital_allocator`, `other` |
| `exposure_strength` | `core`, `material`, `peripheral` |
| `confidence` | `high`, `medium`, `low` |
| `dedup_method` | `hash_exact`, `content_similarity` |

---

## 7. Entity Relationships

```
NormalizedItem (1) ──→ (many) AnalyticalOutput
AnalyticalOutput (1) ──→ (0..1) StructuralExposureRecord
AnalyticalOutput (many) ──→ (1) DailyDigestRecord (via high_importance_items)
NormalizedItem (many) ──→ (1) DeduplicationRecord (via canonical_item_id)
```

- A NormalizedItem may be re-analyzed multiple times (producing multiple AnalyticalOutputs with different `analysis_version` values).
- A StructuralExposureRecord is only created for AnalyticalOutputs with `importance` of `medium` or `high`.
- A DailyDigestRecord references AnalyticalOutputs included in that day's digest.
- DeduplicationRecords preserve the lineage of merged items.
