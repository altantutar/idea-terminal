"""Stats and cost overview API endpoints."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from idea_factory.db import repository as repo
from idea_factory.web.deps import get_conn

router = APIRouter(tags=["stats"])


@router.get("/stats/overview")
def stats_overview(conn: sqlite3.Connection = Depends(get_conn)):
    return repo.get_stats(conn)


@router.get("/stats/costs")
def stats_costs(conn: sqlite3.Connection = Depends(get_conn)):
    return repo.get_cost_summary(conn)


@router.get("/stats/scoreboard")
def stats_scoreboard(conn: sqlite3.Connection = Depends(get_conn)):
    return repo.get_scoreboard(conn)
