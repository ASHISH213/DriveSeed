"""Server-Sent Events (SSE) router providing live task updates."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.api.auth import get_current_user
from app.models.user import User
from app.services.events import EventBroadcaster, get_event_broadcaster

router = APIRouter(tags=["Events"])


@router.get("/events")
@router.get("/api/events")
async def events_stream(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    broadcaster: Annotated[EventBroadcaster, Depends(get_event_broadcaster)],
    limit: int | None = Query(
        default=None,
        description="Optional limit on number of events/pings to stream before closing",
    ),
) -> StreamingResponse:
    """Stream live task progress and lifecycle updates via Server-Sent Events."""
    return StreamingResponse(
        broadcaster.subscribe(
            user_id=str(current_user.id),
            request=request,
            max_events=limit,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
