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


class ItemDetailResponse(BaseModel):
    item: ItemDetail
    analysis: AnalysisDetail | None
