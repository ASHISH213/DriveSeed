"""Media streaming API router supporting HTTP Range requests (RFC 7233)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse

from app.api.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.rate_limit import StreamConcurrencyLimiter, get_stream_concurrency_limiter
from app.interfaces.streamer import Streamer
from app.models.user import User
from app.services.stream import MediaProxyDisabledError, ProxyStreamer

router = APIRouter(tags=["Streaming"])


def get_streamer(settings: Annotated[Settings, Depends(get_settings)]) -> Streamer:
    """Dependency provider returning active Streamer instance for the profile."""
    if settings.PROFILE == "colab":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MEDIA_PROXY_DISABLED",
                    "message": "Media proxying is disabled in colab profile",
                }
            },
        )
    return ProxyStreamer(settings=settings)


@router.get("/stream/{file_id}")
@router.get("/api/stream/{file_id}")
async def stream_media(
    file_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    streamer: Annotated[Streamer, Depends(get_streamer)],
    stream_limiter: Annotated[StreamConcurrencyLimiter, Depends(get_stream_concurrency_limiter)],
) -> Response:
    """Stream stored audio/video files supporting 206 Partial Content range seeking."""
    await stream_limiter.acquire(user_id=str(current_user.id), file_id=file_id)

    range_header = request.headers.get("Range")

    try:
        stream_resp = await streamer.stream(
            user=current_user,
            file_id=file_id,
            range_header=range_header,
        )
        if stream_resp.status_code == 416:
            await stream_limiter.release(user_id=str(current_user.id), file_id=file_id)
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers=stream_resp.headers,
            )
    except FileNotFoundError:
        await stream_limiter.release(user_id=str(current_user.id), file_id=file_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"File with ID '{file_id}' was not found in storage",
                }
            },
        ) from None
    except MediaProxyDisabledError:
        await stream_limiter.release(user_id=str(current_user.id), file_id=file_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MEDIA_PROXY_DISABLED",
                    "message": "Media proxying is disabled in colab profile",
                }
            },
        ) from None
    except Exception:
        await stream_limiter.release(user_id=str(current_user.id), file_id=file_id)
        raise

    async def cleanup_iterator() -> AsyncIterator[bytes]:
        try:
            async for chunk in stream_resp.content_iterator:
                yield chunk
        finally:
            await stream_limiter.release(user_id=str(current_user.id), file_id=file_id)

    return StreamingResponse(
        content=cleanup_iterator(),
        status_code=stream_resp.status_code,
        headers=stream_resp.headers,
        media_type=stream_resp.headers.get("Content-Type", "application/octet-stream"),
    )
