"""Run management endpoints — start / stop / status."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from idea_factory.web.runner import RunState, create_run, get_run_state, stop_run

router = APIRouter(tags=["runs"])


class RunStartPayload(BaseModel):
    region: str = "Global"
    domains: list[str] = ["Software engineering"]
    constraints: str = ""
    claude_check: bool = False
    mode: str = "interactive"  # interactive | livestream


@router.post("/runs/start")
async def start_run(payload: RunStartPayload):
    state = create_run(
        region=payload.region,
        domains=payload.domains,
        constraints=payload.constraints,
        claude_check=payload.claude_check,
    )
    # Launch the loop in a background thread
    asyncio.ensure_future(asyncio.to_thread(state.run))
    return {"run_id": state.run_id, "status": "started"}


@router.get("/runs/{run_id}/status")
def run_status(run_id: str):
    state = get_run_state(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run_id": state.run_id,
        "status": state.status,
        "loop_num": state.loop_num,
        "total_ideas": state.total_ideas,
        "total_winners": state.total_winners,
    }


@router.post("/runs/{run_id}/stop")
def run_stop(run_id: str):
    state = get_run_state(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Run not found")
    stop_run(run_id)
    return {"run_id": run_id, "status": "stopping"}
