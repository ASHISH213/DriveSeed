"""Storage quota API router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import get_current_user
from app.models.user import User
from app.schemas.storage import StorageResponse
from app.services.library import DriveNotConnectedError
from app.services.storage import StorageService

router = APIRouter(prefix="/api/storage", tags=["Storage"])


def get_storage_service() -> StorageService:
    """Dependency provider returning StorageService instance."""
    return StorageService()


@router.get("", response_model=StorageResponse)
async def get_storage(
    current_user: Annotated[User, Depends(get_current_user)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
) -> StorageResponse:
    """Retrieve Google Drive storage quota metrics for the current user."""
    try:
        return await storage_service.get_storage_quota(user=current_user)
    except DriveNotConnectedError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "drive_not_connected", "message": str(err)}},
        ) from err
