"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

_WEB_DIR = Path(__file__).parent


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    from idea_factory.web.api import ideas, stats, runs, feedback, provider
    from idea_factory.web import pages, sse

    app = FastAPI(title="Idea Factory", docs_url="/docs")

    # --- API routers ---
    app.include_router(ideas.router, prefix="/api")
    app.include_router(stats.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(feedback.router, prefix="/api")
    app.include_router(provider.router, prefix="/api")

    # --- SSE ---
    app.include_router(sse.router)

    # --- Page routes ---
    app.include_router(pages.router)

    # --- Static files ---
    app.mount("/static", StaticFiles(directory=_WEB_DIR / "static"), name="static")

    return app
