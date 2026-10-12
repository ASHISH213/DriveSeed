"""Tasks API router handling task creation, retrieval, and lifecycle transitions."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.db import get_db_session
from app.core.rate_limit import SlidingWindowRateLimiter, get_tasks_rate_limiter
from app.models.user import User
from app.schemas.task import (
    TaskActionResponse,
    TaskCreateRequest,
    TaskResponse,
    TaskStartRequest,
)
from app.services.task import (
    InsufficientStorageError,
    MaxActiveTasksExceededError,
    TaskNotFoundError,
    TaskService,
)
from app.services.task_state import InvalidStateTransitionError

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def get_task_service() -> TaskService:
    """Dependency provider for TaskService."""
    from app.services.factory import get_task_queue

    return TaskService(queue=get_task_queue())


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    request: TaskCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
    tasks_limiter: Annotated[SlidingWindowRateLimiter, Depends(get_tasks_rate_limiter)],
) -> TaskResponse:
    """Submit a new download task."""
    await tasks_limiter.check(str(current_user.id))

    try:
        task = await task_service.create_task(
            db=db,
            user=current_user,
            request=request,
        )
        return TaskResponse.model_validate(task)
    except MaxActiveTasksExceededError as err:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "task_cap_exceeded",
                    "message": f"Maximum active tasks limit ({err.limit}) reached. "
                    "Please wait for an active task to finish or cancel one.",
                }
            },
        ) from err
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_input", "message": str(err)}},
        ) from err


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> list[TaskResponse]:
    """Retrieve all tasks for authenticated user."""
    tasks = await task_service.list_tasks(db=db, user=current_user)
    return [TaskResponse.model_validate(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """Retrieve a single task by ID."""
    try:
        task = await task_service.get_task(db=db, user=current_user, task_id=task_id)
        return TaskResponse.model_validate(task)
    except TaskNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": str(err)}},
        ) from err


@router.post("/{task_id}/pause", response_model=TaskActionResponse)
async def pause_task(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskActionResponse:
    """Pause an active downloading task."""
    try:
        task = await task_service.pause_task(db=db, user=current_user, task_id=task_id)
        return TaskActionResponse(
            id=task.id,
            state=task.state,
            message="Task paused successfully",
        )
    except TaskNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": str(err)}},
        ) from err
    except InvalidStateTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_transition", "message": str(err)}},
        ) from err


@router.post("/{task_id}/resume", response_model=TaskActionResponse)
async def resume_task(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskActionResponse:
    """Resume a paused task."""
    try:
        task = await task_service.resume_task(db=db, user=current_user, task_id=task_id)
        return TaskActionResponse(
            id=task.id,
            state=task.state,
            message="Task resumed successfully",
        )
    except TaskNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": str(err)}},
        ) from err
    except InvalidStateTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_transition", "message": str(err)}},
        ) from err


@router.post("/{task_id}/cancel", response_model=TaskActionResponse)
async def cancel_task(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskActionResponse:
    """Cancel a task."""
    try:
        task = await task_service.cancel_task(db=db, user=current_user, task_id=task_id)
        return TaskActionResponse(
            id=task.id,
            state=task.state,
            message="Task cancelled successfully",
        )
    except TaskNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": str(err)}},
        ) from err
    except InvalidStateTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_transition", "message": str(err)}},
        ) from err


@router.post("/{task_id}/retry", response_model=TaskActionResponse)
async def retry_task(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskActionResponse:
    """Retry a failed task, resetting its error and re-queueing it."""
    try:
        task = await task_service.retry_task(db=db, user=current_user, task_id=task_id)
        return TaskActionResponse(
            id=task.id,
            state=task.state,
            message="Task reset and queued for retry",
        )
    except TaskNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": str(err)}},
        ) from err
    except MaxActiveTasksExceededError as err:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "task_cap_exceeded",
                    "message": f"Maximum active tasks limit ({err.limit}) reached. "
                    "Please wait for an active task to finish or cancel one.",
                }
            },
        ) from err
    except InvalidStateTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_transition", "message": str(err)}},
        ) from err


@router.post("/{task_id}/start", response_model=TaskResponse)
async def start_task(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
    request: TaskStartRequest | None = None,
) -> TaskResponse:
    """Start task with chosen files and destination folder, verifying Drive free space."""
    try:
        task = await task_service.start_task(
            db=db,
            user=current_user,
            task_id=task_id,
            request=request,
        )
        return TaskResponse.model_validate(task)
    except TaskNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": str(err)}},
        ) from err
    except InvalidStateTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_transition", "message": str(err)}},
        ) from err
    except InsufficientStorageError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "insufficient_storage", "message": str(err)}},
        ) from err
