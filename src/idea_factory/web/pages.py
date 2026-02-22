"""Server-rendered HTML page routes."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from idea_factory.db import repository as repo
from idea_factory.web.deps import get_conn

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def _parse_tags(tags):
    if isinstance(tags, str):
        try:
            return json.loads(tags)
        except json.JSONDecodeError:
            return []
    return tags or []


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    status: str | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
):
    ideas = repo.list_ideas(conn, status)
    for idea in ideas:
        idea["tags"] = _parse_tags(idea.get("tags"))
    stats = repo.get_stats(conn)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "ideas": ideas,
            "stats": stats,
            "current_status": status,
        },
    )


@router.get("/ideas/{idea_id}", response_class=HTMLResponse)
def idea_detail(
    request: Request,
    idea_id: int,
    conn: sqlite3.Connection = Depends(get_conn),
):
    idea = repo.get_idea(conn, idea_id)
    if not idea:
        return HTMLResponse("<h1>Idea not found</h1>", status_code=404)
    idea = dict(idea)
    idea["tags"] = _parse_tags(idea.get("tags"))
    outputs = repo.get_agent_outputs(conn, idea_id)
    # Parse output JSON
    parsed_outputs = []
    for o in outputs:
        d = dict(o)
        raw = d.get("output", d.get("output_json", {}))
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                pass
        d["output"] = raw
        parsed_outputs.append(d)
    return templates.TemplateResponse(
        "idea_detail.html",
        {
            "request": request,
            "idea": idea,
            "outputs": parsed_outputs,
        },
    )


@router.get("/run", response_class=HTMLResponse)
def run_page(request: Request):
    from idea_factory.cli import DOMAIN_CHOICES
    from idea_factory.web.deps import get_settings

    settings = get_settings()
    return templates.TemplateResponse(
        "run.html",
        {
            "request": request,
            "domain_choices": DOMAIN_CHOICES,
            "provider": settings.llm_provider,
            "model": settings.model,
            "has_key": bool(settings.active_api_key()),
        },
    )


@router.get("/costs", response_class=HTMLResponse)
def costs_page(
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
):
    summary = repo.get_cost_summary(conn)
    return templates.TemplateResponse(
        "costs.html",
        {
            "request": request,
            "summary": summary,
        },
    )
