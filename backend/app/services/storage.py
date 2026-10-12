"""Storage service for calculating and providing user storage metrics."""

import logging

from app.core.config import get_settings
from app.interfaces.storage import StorageBackend
from app.models.user import User
from app.schemas.storage import StorageResponse
from app.services.library import DriveNotConnectedError

logger = logging.getLogger(__name__)


class StorageService:
    """Service handling storage quota metric retrieval."""

    def __init__(self, storage: StorageBackend | None = None) -> None:
        self._storage = storage

    def _get_storage(self) -> StorageBackend:
        if self._storage is not None:
            return self._storage
        from app.services.factory import get_storage_backend

        return get_storage_backend(get_settings())

    @staticmethod
    def _verify_drive_connected(user: User) -> None:
        if get_settings().PROFILE == "colab":
            return
        if not user.drive_refresh_token_enc:
            raise DriveNotConnectedError()

    async def get_storage_quota(self, user: User) -> StorageResponse:
        """Fetch total and used storage from Google Drive and compute metrics."""
        self._verify_drive_connected(user)
        storage = self._get_storage()
        quota = await storage.quota(user)

        used = max(0, quota.used_bytes)
        total = max(0, quota.total_bytes)
        free = max(0, total - used)
        percent = (used / total * 100.0) if total > 0 else 0.0
        percent = min(100.0, max(0.0, percent))

        return StorageResponse(
            used_bytes=used,
            total_bytes=total,
            free_bytes=free,
            percent_used=round(percent, 1),
        )
