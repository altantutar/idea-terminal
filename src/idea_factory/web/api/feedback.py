"""Feedback submission endpoint — signals the runner to continue."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from idea_factory.web.runner import get_run_state

router = APIRouter(tags=["feedback"])


class FeedbackPayload(BaseModel):
    decision: str
    rating: int = 5
    tags: list[str] = []
    note: str = ""


@router.post("/feedback/{run_id}")
def submit_feedback(run_id: str, payload: FeedbackPayload):
    state = get_run_state(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Run not found")
    state.submit_feedback(payload.model_dump())
    return {"ok": True}
