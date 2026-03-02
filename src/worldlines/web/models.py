"""Pydantic v2 response models for the Worldlines web API."""

from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
class StatsResponse(BaseModel):
    total_items: int
    total_analyses: int
    total_digests: int
    latest_digest_date: str | None
    dimension_breakdown: dict[str, int]
    change_type_distribution: dict[str, int]
    importance_distribution: dict[str, int]


# ---------------------------------------------------------------------------
# Digests
# ---------------------------------------------------------------------------
class DigestSummary(BaseModel):
    id: str
    digest_date: str
    item_count: int
    dimension_breakdown: dict[str, int]
    change_type_distribution: dict[str, int]
    sent_at: str


class DigestDetail(DigestSummary):
    high_importance_items: list[dict]
    summary_en: str | None = None
    summary_zh: str | None = None
    message_text: str
    telegram_message_ids: list[int]


class DigestListResponse(BaseModel):
    digests: list[DigestSummary]
    total: int
    page: int
    per_page: int
    pages: int


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------
class ItemSummary(BaseModel):
    id: str
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
    eligible_for_exposure_mapping: bool


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
    dedup_hash: str


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
    eligible_for_exposure_mapping: bool


class ExposureEntry(BaseModel):
    ticker: str
    exposure_type: str
    business_role: str
    exposure_strength: str
    confidence: str
    dimensions_implicated: list[str]
    rationale: str


class ExposureDetail(BaseModel):
    id: str
    analysis_id: str
    item_id: str
    exposures: list[ExposureEntry]
    skipped_reason: str | None = None
    mapped_at: str


class TemporalLinkEntry(BaseModel):
    id: str
    direction: str          # 'outgoing' | 'incoming'
    link_type: str
    rationale: str
    created_at: str
    linked_item_id: str
    linked_item_title: str
    linked_item_source: str
    linked_item_timestamp: str


class ItemDetailResponse(BaseModel):
    item: ItemDetail
    analysis: AnalysisDetail | None
    exposure: ExposureDetail | None = None
    temporal_links: list[TemporalLinkEntry] | None = None


# ---------------------------------------------------------------------------
# Exposures
# ---------------------------------------------------------------------------
class ExposureListResponse(BaseModel):
    exposures: list[ExposureDetail]
    total: int
    page: int
    per_page: int
    pages: int


# ---------------------------------------------------------------------------
# Ticker index
# ---------------------------------------------------------------------------
class TickerIndexEntry(BaseModel):
    ticker: str
    article_count: int
    last_mapped_at: str


class TickerIndexResponse(BaseModel):
    tickers: list[TickerIndexEntry]
    total: int


# ---------------------------------------------------------------------------
# Ticker exposures
# ---------------------------------------------------------------------------
class TickerExposureEntry(BaseModel):
    item_id: str
    item_title: str
    source_name: str
    item_timestamp: str
    analysis_id: str
    analyzed_at: str
    analysis_summary: str
    importance: str
    mapped_at: str
    exposure_type: str
    business_role: str
    exposure_strength: str
    confidence: str
    dimensions_implicated: list[str]
    rationale: str


class TickerExposureResponse(BaseModel):
    ticker: str
    synthesis: None = None
    entries: list[TickerExposureEntry]
    total: int
    page: int
    per_page: int
    pages: int


# ---------------------------------------------------------------------------
# Periodic Summaries
# ---------------------------------------------------------------------------
class PeriodicSummary(BaseModel):
    id: str
    period_label: str
    window_days: int
    since: str
    until: str
    item_count: int
    dimension_breakdown: dict[str, int]
    change_type_distribution: dict[str, int]
    summary_en: str | None = None
    summary_zh: str | None = None
    sent_at: str


class PeriodicSummaryListResponse(BaseModel):
    summaries: list[PeriodicSummary]
    total: int
    page: int
    per_page: int
    pages: int


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------
class DimensionSignal(BaseModel):
    id: str
    title: str
    timestamp: str
    change_type: str


class DimensionCard(BaseModel):
    dimension: str
    item_count_30d: int
    change_type_distribution: dict[str, int]
    top_entities: list[str]
    recent_items: list[DimensionSignal]


class DimensionOverview(BaseModel):
    dimensions: list[DimensionCard]


class DimensionDetailItem(BaseModel):
    id: str
    title: str
    summary: str
    timestamp: str
    change_type: str
    importance: str
    source_name: str


class DimensionDetail(BaseModel):
    dimension: str
    item_count_7d: int
    item_count_30d: int
    item_count_90d: int
    change_type_distribution: dict[str, int]
    top_entities: list[str]
    recent_items: list[DimensionDetailItem]


# ---------------------------------------------------------------------------
# Pipeline Runs
# ---------------------------------------------------------------------------
class PipelineRun(BaseModel):
    id: str
    run_type: str
    started_at: str
    finished_at: str
    status: str
    result: dict
    error: str | None


class PipelineRunListResponse(BaseModel):
    runs: list[PipelineRun]
    total: int
    page: int
    per_page: int
    pages: int
