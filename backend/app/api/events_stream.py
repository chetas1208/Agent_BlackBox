"""SSE endpoint for real-time event streaming."""
from __future__ import annotations

import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.core.redis import get_redis
from app.core.config import get_settings

router = APIRouter(prefix="/api/sessions", tags=["events-stream"])


@router.get("/{session_id}/events/stream")
async def event_stream(session_id: str, request: Request):
    settings = get_settings()

    async def generate():
        r = await get_redis()
        pubsub = r.pubsub()
        channel = f"{settings.redis_prefix}events:stream:{session_id}"
        await pubsub.subscribe(channel)

        try:
            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message and message["type"] == "message":
                    data = message["data"]
                    yield f"data: {data}\n\n"
                else:
                    yield f": keepalive\n\n"
                    await asyncio.sleep(1)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
