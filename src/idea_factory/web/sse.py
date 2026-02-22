"""Server-Sent Events endpoint for streaming run progress."""

from __future__ import annotations

import asyncio
import json
import queue

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from idea_factory.web.runner import get_run_state

router = APIRouter(tags=["sse"])


@router.get("/sse/{run_id}")
async def sse_stream(run_id: str):
    state = get_run_state(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        while True:
            try:
                event = state.events.get_nowait()
            except queue.Empty:
                if state.status in ("completed", "error"):
                    # Drain remaining events
                    while not state.events.empty():
                        try:
                            event = state.events.get_nowait()
                            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
                        except queue.Empty:
                            break
                    yield "event: done\ndata: {}\n\n"
                    return
                await asyncio.sleep(0.3)
                continue
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
