"""FastAPI application factory for the Worldlines web API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from worldlines.web.config import WebConfig
from worldlines.web.routes import health_router, router


def create_app(config: WebConfig, lifespan=None) -> FastAPI:
    """Build and return a configured FastAPI application."""
    app = FastAPI(title="Worldlines", docs_url="/api/docs", lifespan=lifespan)
    app.state.database_path = config.database_path
    app.include_router(health_router)
    app.include_router(router, prefix="/api/v1")

    static_path = Path(config.static_dir)
    if static_path.is_dir():
        app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")

    return app
