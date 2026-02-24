"""FastAPI application factory for the Worldlines web API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse
from starlette.types import Scope

from worldlines.web.config import WebConfig
from worldlines.web.routes import health_router, router


class _SPAStaticFiles(StaticFiles):
    """StaticFiles that falls back to index.html for unknown paths (SPA routing)."""

    async def get_response(self, path: str, scope: Scope) -> FileResponse:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


def create_app(config: WebConfig, lifespan=None) -> FastAPI:
    """Build and return a configured FastAPI application."""
    app = FastAPI(title="Worldlines", docs_url="/api/docs", lifespan=lifespan)
    app.state.database_path = config.database_path
    app.include_router(health_router)
    app.include_router(router, prefix="/api/v1")

    static_path = Path(config.static_dir)
    if static_path.is_dir():
        app.mount("/", _SPAStaticFiles(directory=str(static_path), html=True), name="static")

    return app
