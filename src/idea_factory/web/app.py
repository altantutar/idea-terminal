"""FastAPI application factory."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

_WEB_DIR = Path(__file__).parent


def _file_hash(path: Path) -> str:
    """Return a short hash of a file's contents for cache-busting."""
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()[:8]  # noqa: S324
    except FileNotFoundError:
        return "0"


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    from idea_factory.web import pages, sse
    from idea_factory.web.api import feedback, ideas, provider, runs, stats

    app = FastAPI(title="Idea Factory", docs_url="/docs")

    # --- Cache-busting hashes for static files ---
    static_dir = _WEB_DIR / "static"
    app.state.static_versions = {
        "style.css": _file_hash(static_dir / "style.css"),
        "app.js": _file_hash(static_dir / "app.js"),
    }

    @app.middleware("http")
    async def no_cache_static(request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

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
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    return app
