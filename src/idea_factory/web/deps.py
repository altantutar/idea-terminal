"""FastAPI dependency injection — DB connection and settings."""

from __future__ import annotations

import sqlite3
from typing import Generator

from idea_factory.config import Settings
from idea_factory.db.connection import get_db

_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_conn() -> Generator[sqlite3.Connection, None, None]:
    """Yield a per-request SQLite connection, auto-closed afterwards."""
    settings = get_settings()
    conn = get_db(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()
