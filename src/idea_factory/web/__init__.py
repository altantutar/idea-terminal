"""Web frontend for Idea Factory — FastAPI + Jinja2 + HTMX."""

from __future__ import annotations


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the web server via uvicorn."""
    import uvicorn

    from idea_factory.web.app import create_app

    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
