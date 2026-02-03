"""API route handlers for the Worldlines web API."""

from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException, Query, Request

from worldlines.web.models import (
    DigestDetail,
    DigestListResponse,
    ItemDetailResponse,
    ItemListResponse,
    ItemSummary,
    StatsResponse,
)
from worldlines.web.queries import (
    get_digest_by_date,
    get_item_by_id,
    get_stats,
    list_digests,
    list_items,
)

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
def stats(request: Request) -> StatsResponse:
    database_path = request.app.state.database_path
    data = get_stats(database_path)
    return StatsResponse(**data)


@router.get("/digests", response_model=DigestListResponse)
def digests(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> DigestListResponse:
    database_path = request.app.state.database_path
    rows, total = list_digests(database_path, page=page, per_page=per_page)
    pages = math.ceil(total / per_page) if total else 0
    return DigestListResponse(
        digests=rows,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/digests/{date}", response_model=DigestDetail)
def digest_by_date(request: Request, date: str) -> DigestDetail:
    database_path = request.app.state.database_path
    data = get_digest_by_date(database_path, date)
    if data is None:
        raise HTTPException(status_code=404, detail="Digest not found")
    return DigestDetail(**data)


@router.get("/items", response_model=ItemListResponse)
def items(
    request: Request,
    dimension: str | None = None,
    change_type: str | None = None,
    importance: str | None = None,
    time_horizon: str | None = None,
    source_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort: str = "analyzed_at",
    order: str = "desc",
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> ItemListResponse:
    database_path = request.app.state.database_path

    filters: dict[str, str] = {}
    if dimension is not None:
        filters["dimension"] = dimension
    if change_type is not None:
        filters["change_type"] = change_type
    if importance is not None:
        filters["importance"] = importance
    if time_horizon is not None:
        filters["time_horizon"] = time_horizon
    if source_type is not None:
        filters["source_type"] = source_type
    if date_from is not None:
        filters["date_from"] = date_from
    if date_to is not None:
        filters["date_to"] = date_to

    rows, total = list_items(
        database_path,
        filters=filters,
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
    )
    pages = math.ceil(total / per_page) if total else 0
    items_out = [ItemSummary(**r) for r in rows]
    return ItemListResponse(
        items=items_out,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/items/{item_id}", response_model=ItemDetailResponse)
def item_by_id(request: Request, item_id: str) -> ItemDetailResponse:
    database_path = request.app.state.database_path
    data = get_item_by_id(database_path, item_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return ItemDetailResponse(**data)
