"""Personal API tokens router for programmatic access."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, get_token_service
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.token import (
    ApiTokenCreatedResponse,
    ApiTokenCreateRequest,
    ApiTokenResponse,
)
from app.services.token import ApiTokenService

router = APIRouter(prefix="/api/tokens", tags=["Tokens"])


@router.post(
    "",
    response_model=ApiTokenCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_token(
    payload: ApiTokenCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    token_service: Annotated[ApiTokenService, Depends(get_token_service)],
) -> ApiTokenCreatedResponse:
    """Generate a new personal API token.

    The raw secret token is returned ONLY in this response and cannot be retrieved again.
    """
    token_record, raw_secret = await token_service.create_token(
        db=db,
        user_id=current_user.id,
        label=payload.label,
    )

    return ApiTokenCreatedResponse(
        id=token_record.id,
        prefix=token_record.prefix,
        label=token_record.label,
        created_at=token_record.created_at,
        last_used_at=token_record.last_used_at,
        token=raw_secret,
    )


@router.get(
    "",
    response_model=list[ApiTokenResponse],
)
async def list_tokens(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    token_service: Annotated[ApiTokenService, Depends(get_token_service)],
) -> list[ApiTokenResponse]:
    """List all active personal API tokens for the authenticated user."""
    tokens = await token_service.list_tokens(db=db, user_id=current_user.id)
    return [ApiTokenResponse.model_validate(tok) for tok in tokens]


@router.delete(
    "/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_token(
    token_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    token_service: Annotated[ApiTokenService, Depends(get_token_service)],
) -> Response:
    """Revoke and permanently delete a personal API token."""
    revoked = await token_service.revoke_token(
        db=db,
        user_id=current_user.id,
        token_id=token_id,
    )

    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "not_found",
                    "message": "API token not found",
                }
            },
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
