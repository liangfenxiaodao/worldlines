"""API route handlers for the Worldlines web API."""

from __future__ import annotations

import logging
import math
import sqlite3

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from worldlines.storage.connection import get_connection
from worldlines.web.models import (
    DigestDetail,
    DigestListResponse,
    ItemDetailResponse,
    ItemListResponse,
    ItemSummary,
    PipelineRunListResponse,
    StatsResponse,
)
from worldlines.web.queries import (
    get_digest_by_date,
    get_item_by_id,
    get_stats,
    list_digests,
    list_items,
    list_pipeline_runs,
)

logger = logging.getLogger(__name__)

router = APIRouter()
health_router = APIRouter()


@health_router.get("/health")
def health(request: Request) -> JSONResponse:
    """Check database connectivity and return health status."""
    database_path = request.app.state.database_path
    try:
        with get_connection(database_path) as conn:
            conn.execute("SELECT 1")
        return JSONResponse({"status": "healthy", "database": "ok"})
    except (sqlite3.Error, OSError) as exc:
        logger.warning("Health check failed: %s", exc)
        return JSONResponse(
            {"status": "unhealthy", "database": "error", "detail": str(exc)},
            status_code=503,
        )


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


@router.get("/runs", response_model=PipelineRunListResponse)
def runs(
    request: Request,
    run_type: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
) -> PipelineRunListResponse:
    database_path = request.app.state.database_path
    rows, total = list_pipeline_runs(
        database_path, run_type=run_type, page=page, per_page=per_page,
    )
    pages = math.ceil(total / per_page) if total else 0
    return PipelineRunListResponse(
        runs=rows,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )
