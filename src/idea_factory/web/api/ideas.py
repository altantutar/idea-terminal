"""Idea list and detail API endpoints."""

from __future__ import annotations

import json
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from idea_factory.db import repository as repo
from idea_factory.web.deps import get_conn

router = APIRouter(tags=["ideas"])


def _parse_idea(idea: dict) -> dict:
    """Normalise an idea dict for JSON serialisation."""
    tags = idea.get("tags", "[]")
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError:
            tags = []
    idea["tags"] = tags
    return idea


@router.get("/ideas")
def list_ideas(
    status: Optional[str] = None,
    conn: sqlite3.Connection = Depends(get_conn),
):
    ideas = repo.list_ideas(conn, status)
    return [_parse_idea(i) for i in ideas]


@router.get("/ideas/{idea_id}")
def get_idea(
    idea_id: int,
    conn: sqlite3.Connection = Depends(get_conn),
):
    idea = repo.get_idea(conn, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    outputs = repo.get_agent_outputs(conn, idea_id)
    # Normalise output_json -> output for each agent output
    for o in outputs:
        raw = o.get("output", o.get("output_json", {}))
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                pass
        o["output"] = raw
    return {"idea": _parse_idea(dict(idea)), "agent_outputs": outputs}
