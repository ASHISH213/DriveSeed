"""Unit tests for rate limiters, per-user task caps, and stream concurrency caps."""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from fastapi import status

from app.core.rate_limit import (
    RateLimitExceededError,
    SlidingWindowRateLimiter,
    StreamCapExceededError,
    StreamConcurrencyLimiter,
)
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreateRequest
from app.services.task import MaxActiveTasksExceededError, TaskService
from app.services.task_state import TaskState
from tests.fakes.fake_db import FakeAsyncSession


@pytest.mark.asyncio
async def test_sliding_window_rate_limiter_allows_and_blocks() -> None:
    """Verify SlidingWindowRateLimiter enforces burst threshold and sets Retry-After."""
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=10.0)

    # 3 requests succeed
    await limiter.check("user_1")
    await limiter.check("user_1")
    await limiter.check("user_1")

    # 4th request within window must raise RateLimitExceededError (429)
    with pytest.raises(RateLimitExceededError) as exc_info:
        await limiter.check("user_1")

    err = exc_info.value
    assert err.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in err.headers
    retry_after = int(err.headers["Retry-After"])
    assert 1 <= retry_after <= 10
    detail = err.detail
    assert detail["error"]["code"] == "rate_limit_exceeded"

    # Distinct user is unaffected
    await limiter.check("user_2")


@pytest.mark.asyncio
async def test_sliding_window_rate_limiter_window_expiration() -> None:
    """Verify limiter permits requests after window expiration."""
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=0.1)

    await limiter.check("key_a")
    with pytest.raises(RateLimitExceededError):
        await limiter.check("key_a")

    # Wait for window to expire
    await asyncio.sleep(0.12)
    # Now request succeeds again
    await limiter.check("key_a")


@pytest.mark.asyncio
async def test_stream_concurrency_limiter_distinct_files() -> None:
    """Verify limiter caps distinct files per user, but allows concurrent chunks on same file."""
    limiter = StreamConcurrencyLimiter(max_concurrent=2)

    # File 1: first request and additional concurrent range request
    await limiter.acquire("user_a", "file_1")
    await limiter.acquire("user_a", "file_1")

    # File 2: second distinct active file
    await limiter.acquire("user_a", "file_2")

    # File 3: third distinct active file exceeds limit (max_concurrent=2)
    with pytest.raises(StreamCapExceededError) as exc_info:
        await limiter.acquire("user_a", "file_3")

    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert exc_info.value.detail["error"]["code"] == "stream_cap_exceeded"

    # Other user can stream file 3 without conflict
    await limiter.acquire("user_b", "file_3")

    # Release file 2
    await limiter.release("user_a", "file_2")

    # Now user_a can stream file 3
    await limiter.acquire("user_a", "file_3")

    # Releasing file 1 once still keeps 1 connection active
    await limiter.release("user_a", "file_1")
    # Trying to add file 4 still fails because file 1 and file 3 are active
    with pytest.raises(StreamCapExceededError):
        await limiter.acquire("user_a", "file_4")

    # Releasing file 1 second connection completely closes file 1
    await limiter.release("user_a", "file_1")
    # Now user_a can acquire file 4
    await limiter.acquire("user_a", "file_4")


@pytest.mark.asyncio
async def test_task_service_active_tasks_cap() -> None:
    """Verify TaskService enforces MAX_ACTIVE_TASKS_PER_USER for creating and retrying tasks."""
    db = FakeAsyncSession()
    service = TaskService()

    user = User(
        id=uuid.uuid4(),
        google_sub="sub-cap-test",
        email="cap@example.com",
        created_at=datetime.now(UTC),
    )
    db.add(user)

    # Create 3 active tasks (the default MAX_ACTIVE_TASKS_PER_USER is 3)
    t1 = await service.create_task(
        db, user, TaskCreateRequest(source_uri="https://example.com/file1.zip")
    )
    t2 = await service.create_task(
        db, user, TaskCreateRequest(source_uri="https://example.com/file2.zip")
    )
    t3 = await service.create_task(
        db, user, TaskCreateRequest(source_uri="https://example.com/file3.zip")
    )

    assert t1.state == TaskState.QUEUED.value
    assert t2.state == TaskState.QUEUED.value
    assert t3.state == TaskState.QUEUED.value

    # 4th task creation must raise MaxActiveTasksExceededError
    with pytest.raises(MaxActiveTasksExceededError) as exc_info:
        await service.create_task(
            db, user, TaskCreateRequest(source_uri="https://example.com/file4.zip")
        )
    assert exc_info.value.limit == 3

    # Transition t1 to COMPLETED (terminal state)
    t1.state = TaskState.COMPLETED.value
    await db.commit()

    # Now creating a new task succeeds because active count is back to 2
    t4 = await service.create_task(
        db, user, TaskCreateRequest(source_uri="https://example.com/file4.zip")
    )
    assert t4.state == TaskState.QUEUED.value

    # Let's transition t2 to FAILED
    t2.state = TaskState.FAILED.value
    await db.commit()

    # Now active count is 2 (t3 and t4). Retry t2 should succeed
    retried_t2 = await service.retry_task(db, user, t2.id)
    assert retried_t2.state == TaskState.QUEUED.value

    # Active count is 3 again. Now create a failed task t5 directly
    t5 = Task(
        user_id=user.id,
        source_type="url",
        source_uri="https://example.com/file5.zip",
        name="file5",
        state=TaskState.FAILED.value,
        progress=0.0,
    )
    db.add(t5)
    await db.commit()

    # Retrying t5 when already at 3 active tasks must raise MaxActiveTasksExceededError
    with pytest.raises(MaxActiveTasksExceededError):
        await service.retry_task(db, user, t5.id)
