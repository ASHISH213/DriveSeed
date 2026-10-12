"""RSS Subscriptions API router for automated feed downloads."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.tasks import get_task_service
from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.rss import (
    RssFeedItemPreview,
    RssPreviewRequest,
    RssPreviewResponse,
    RssSubscriptionCreate,
    RssSubscriptionResponse,
    RssSyncResponse,
)
from app.services.rss import RssService
from app.services.task import TaskService

router = APIRouter(prefix="/api/rss", tags=["RSS"])


def get_rss_service() -> RssService:
    """Dependency provider returning RssService instance."""
    return RssService()


@router.post(
    "",
    response_model=RssSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription(
    payload: RssSubscriptionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    rss_service: Annotated[RssService, Depends(get_rss_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RssSubscriptionResponse:
    """Create a new automated RSS feed subscription."""
    try:
        sub = await rss_service.create_subscription(
            db=db,
            user_id=current_user.id,
            name=payload.name,
            url=payload.url,
            filter_regex=payload.filter_regex,
            allow_local=settings.DEBUG,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_feed", "message": str(err)}},
        ) from err

    return RssSubscriptionResponse.model_validate(sub)


@router.get(
    "",
    response_model=list[RssSubscriptionResponse],
)
async def list_subscriptions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    rss_service: Annotated[RssService, Depends(get_rss_service)],
) -> list[RssSubscriptionResponse]:
    """List all configured RSS subscriptions for current user."""
    subs = await rss_service.list_subscriptions(db, current_user.id)
    return [RssSubscriptionResponse.model_validate(s) for s in subs]


@router.post(
    "/preview",
    response_model=RssPreviewResponse,
)
async def preview_feed(
    payload: RssPreviewRequest,
    _current_user: Annotated[User, Depends(get_current_user)],
    rss_service: Annotated[RssService, Depends(get_rss_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RssPreviewResponse:
    """Fetch and evaluate a feed URL and regex without saving."""
    try:
        feed_title, total, items = await rss_service.preview_feed(
            url=payload.url,
            filter_regex=payload.filter_regex,
            allow_local=settings.DEBUG,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "preview_failed", "message": str(err)}},
        ) from err

    return RssPreviewResponse(
        feed_title=feed_title,
        total_items=total,
        matching_items=[RssFeedItemPreview.model_validate(i) for i in items],
    )


@router.post(
    "/{subscription_id}/sync",
    response_model=RssSyncResponse,
)
async def sync_subscription(
    subscription_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    rss_service: Annotated[RssService, Depends(get_rss_service)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RssSyncResponse:
    """Poll feed and auto-trigger download tasks for new matching entries."""
    try:
        checked, created, task_ids = await rss_service.sync_subscription(
            db=db,
            user=current_user,
            subscription_id=subscription_id,
            task_service=task_service,
            allow_local=settings.DEBUG,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "sync_failed", "message": str(err)}},
        ) from err

    return RssSyncResponse(
        subscription_id=subscription_id,
        items_checked=checked,
        tasks_created=created,
        created_task_ids=task_ids,
    )


@router.delete(
    "/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_subscription(
    subscription_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    rss_service: Annotated[RssService, Depends(get_rss_service)],
) -> Response:
    """Delete an RSS subscription."""
    deleted = await rss_service.delete_subscription(db, current_user.id, subscription_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Subscription not found"}},
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
