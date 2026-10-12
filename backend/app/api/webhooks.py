"""Webhook endpoints router for task lifecycle notifications."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.webhook import (
    WebhookEndpointCreate,
    WebhookEndpointResponse,
    WebhookTestResponse,
)
from app.services.webhook import WebhookService

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


def get_webhook_service() -> WebhookService:
    """Dependency provider returning WebhookService instance."""
    return WebhookService()


@router.post(
    "",
    response_model=WebhookEndpointResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_webhook(
    payload: WebhookEndpointCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    webhook_service: Annotated[WebhookService, Depends(get_webhook_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WebhookEndpointResponse:
    """Register a new webhook endpoint for task notifications."""
    try:
        endpoint = await webhook_service.create_endpoint(
            db=db,
            user_id=current_user.id,
            url=payload.url,
            secret=payload.secret,
            events=payload.events,
            allow_local=settings.DEBUG,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_url", "message": str(err)}},
        ) from err

    return WebhookEndpointResponse(
        id=endpoint.id,
        url=endpoint.url,
        secret=endpoint.secret,
        events=[e.strip() for e in endpoint.events.split(",")],
        is_active=endpoint.is_active,
        created_at=endpoint.created_at,
    )


@router.get(
    "",
    response_model=list[WebhookEndpointResponse],
)
async def list_webhooks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    webhook_service: Annotated[WebhookService, Depends(get_webhook_service)],
) -> list[WebhookEndpointResponse]:
    """List all registered webhook endpoints for current user."""
    endpoints = await webhook_service.list_endpoints(db, current_user.id)
    return [
        WebhookEndpointResponse(
            id=ep.id,
            url=ep.url,
            secret=ep.secret,
            events=[e.strip() for e in ep.events.split(",")],
            is_active=ep.is_active,
            created_at=ep.created_at,
        )
        for ep in endpoints
    ]


@router.post(
    "/{endpoint_id}/test",
    response_model=WebhookTestResponse,
)
async def test_webhook(
    endpoint_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    webhook_service: Annotated[WebhookService, Depends(get_webhook_service)],
) -> WebhookTestResponse:
    """Send a test ping event to verify webhook delivery and signature."""
    endpoints = await webhook_service.list_endpoints(db, current_user.id)
    endpoint = next((ep for ep in endpoints if ep.id == endpoint_id), None)

    if endpoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Webhook endpoint not found"}},
        )

    success, status_code, message = await webhook_service.send_test_ping(endpoint)
    return WebhookTestResponse(
        success=success,
        status_code=status_code,
        message=message,
    )


@router.delete(
    "/{endpoint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_webhook(
    endpoint_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    webhook_service: Annotated[WebhookService, Depends(get_webhook_service)],
) -> Response:
    """Delete a registered webhook endpoint."""
    deleted = await webhook_service.delete_endpoint(db, current_user.id, endpoint_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Webhook endpoint not found"}},
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
