"""In-memory sliding window rate limiting and stream concurrency controls."""

import asyncio
import math
import time
from collections import defaultdict

from fastapi import HTTPException, status


class RateLimitExceededError(HTTPException):
    """Exception raised when an endpoint request rate limit is exceeded."""

    def __init__(self, limit: int, window_seconds: float, retry_after: int) -> None:
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "rate_limit_exceeded",
                    "message": (
                        f"Rate limit exceeded ({limit} requests per {int(window_seconds)}s). "
                        f"Please try again in {retry_after} seconds."
                    ),
                }
            },
            headers={"Retry-After": str(retry_after)},
        )


class StreamCapExceededError(HTTPException):
    """Exception raised when concurrent streaming slots are fully utilized."""

    def __init__(self, max_concurrent: int) -> None:
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "stream_cap_exceeded",
                    "message": f"Maximum concurrent stream limit ({max_concurrent}) reached. "
                    "Please pause or close another active stream.",
                }
            },
        )


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter tracking request timestamps per client key."""

    def __init__(self, max_requests: int, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        """Verify request volume under window threshold or raise RateLimitExceededError."""
        if self.max_requests <= 0:
            return

        now = time.monotonic()
        cutoff = now - self.window_seconds

        async with self._lock:
            timestamps = self._requests[key]
            # Prune expired timestamps
            valid_timestamps = [t for t in timestamps if t > cutoff]

            if len(valid_timestamps) >= self.max_requests:
                oldest = valid_timestamps[0]
                retry_after = max(1, math.ceil(oldest + self.window_seconds - now))
                self._requests[key] = valid_timestamps
                raise RateLimitExceededError(
                    limit=self.max_requests,
                    window_seconds=self.window_seconds,
                    retry_after=retry_after,
                )

            valid_timestamps.append(now)
            self._requests[key] = valid_timestamps

    def reset(self) -> None:
        """Clear all stored request history (for tests)."""
        self._requests.clear()


class StreamConcurrencyLimiter:
    """Manages active concurrent streams per user, tracking distinct active media files."""

    def __init__(self, max_concurrent: int) -> None:
        self.max_concurrent = max_concurrent
        # user_id -> file_id -> active_connection_count
        self._active: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._lock = asyncio.Lock()

    async def acquire(self, user_id: str, file_id: str) -> None:
        """Acquire a stream slot for the user and file, or raise StreamCapExceededError."""
        if self.max_concurrent <= 0:
            return

        async with self._lock:
            user_files = self._active[user_id]
            # If file is not yet streaming and distinct active files count reaches max_concurrent
            if file_id not in user_files and len(user_files) >= self.max_concurrent:
                raise StreamCapExceededError(max_concurrent=self.max_concurrent)

            user_files[file_id] += 1

    async def release(self, user_id: str, file_id: str) -> None:
        """Release a stream connection slot for the user and file."""
        async with self._lock:
            if user_id in self._active and file_id in self._active[user_id]:
                self._active[user_id][file_id] -= 1
                if self._active[user_id][file_id] <= 0:
                    del self._active[user_id][file_id]
                if not self._active[user_id]:
                    del self._active[user_id]

    def reset(self) -> None:
        """Clear all active streaming records (for tests)."""
        self._active.clear()


_tasks_rate_limiter: SlidingWindowRateLimiter | None = None
_auth_rate_limiter: SlidingWindowRateLimiter | None = None
_stream_concurrency_limiter: StreamConcurrencyLimiter | None = None


def get_tasks_rate_limiter() -> SlidingWindowRateLimiter:
    """Dependency provider for tasks endpoint rate limiter."""
    global _tasks_rate_limiter
    if _tasks_rate_limiter is None:
        from app.core.config import get_settings

        settings = get_settings()
        _tasks_rate_limiter = SlidingWindowRateLimiter(
            max_requests=settings.RATE_LIMIT_TASKS_PER_MINUTE,
            window_seconds=60.0,
        )
    return _tasks_rate_limiter


def get_auth_rate_limiter() -> SlidingWindowRateLimiter:
    """Dependency provider for auth endpoint rate limiter."""
    global _auth_rate_limiter
    if _auth_rate_limiter is None:
        from app.core.config import get_settings

        settings = get_settings()
        _auth_rate_limiter = SlidingWindowRateLimiter(
            max_requests=settings.RATE_LIMIT_AUTH_PER_MINUTE,
            window_seconds=60.0,
        )
    return _auth_rate_limiter


def get_stream_concurrency_limiter() -> StreamConcurrencyLimiter:
    """Dependency provider for stream concurrency limiter."""
    global _stream_concurrency_limiter
    if _stream_concurrency_limiter is None:
        from app.core.config import get_settings

        settings = get_settings()
        _stream_concurrency_limiter = StreamConcurrencyLimiter(
            max_concurrent=settings.MAX_CONCURRENT_STREAMS_PER_USER
        )
    return _stream_concurrency_limiter


def reset_rate_limiters() -> None:
    """Reset limiter states (useful for isolated unit tests)."""
    if _tasks_rate_limiter is not None:
        _tasks_rate_limiter.reset()
    if _auth_rate_limiter is not None:
        _auth_rate_limiter.reset()
    if _stream_concurrency_limiter is not None:
        _stream_concurrency_limiter.reset()
