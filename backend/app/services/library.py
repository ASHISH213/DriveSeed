"""Library management service for Google Drive files and folder operations."""

import logging

from app.core.config import get_settings
from app.interfaces.storage import StorageBackend
from app.models.user import User
from app.schemas.files import (
    BreadcrumbItem,
    FileItemResponse,
    FileListResponse,
)

logger = logging.getLogger(__name__)

FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


class DriveNotConnectedError(Exception):
    """Raised when an operation is attempted without a connected Google Drive account."""

    def __init__(self, message: str = "Google Drive account is not connected") -> None:
        super().__init__(message)


class LibraryService:
    """Service handling library file listing, folder navigation, and mutations."""

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

    async def list_files(
        self,
        user: User,
        folder_id: str | None = None,
        search: str | None = None,
    ) -> FileListResponse:
        """List files and subfolders in folder_id with optional search filtering."""
        self._verify_drive_connected(user)
        storage = self._get_storage()

        # Resolve root folder if folder_id is not specified
        root_id = await storage.ensure_root(user)
        active_folder_id = folder_id if folder_id else root_id

        # Fetch files inside target folder
        stored_items = await storage.list_folder(user, active_folder_id)

        # Filter by search term if provided
        if search and search.strip():
            term = search.strip().lower()
            stored_items = [item for item in stored_items if term in item.name.lower()]

        file_responses: list[FileItemResponse] = []
        for item in stored_items:
            is_folder = item.mime_type == FOLDER_MIME_TYPE
            file_responses.append(
                FileItemResponse(
                    id=item.id,
                    name=item.name,
                    parent_id=item.parent_id,
                    mime_type=item.mime_type,
                    is_folder=is_folder,
                    size_bytes=item.size_bytes,
                    md5=item.md5,
                )
            )

        # Sort: folders first (alphabetical), then files (alphabetical)
        file_responses.sort(key=lambda f: (not f.is_folder, f.name.lower()))

        # Build breadcrumbs hierarchy
        breadcrumbs: list[BreadcrumbItem] = [
            BreadcrumbItem(id=root_id, name="DriveSeed"),
        ]

        # If inside a subfolder, add current folder to breadcrumbs
        if active_folder_id != root_id:
            breadcrumbs.append(
                BreadcrumbItem(
                    id=active_folder_id,
                    name="Folder",  # Will be enriched by client navigation or lookup
                )
            )

        return FileListResponse(
            current_folder_id=active_folder_id,
            breadcrumbs=breadcrumbs,
            files=file_responses,
        )

    async def create_folder(
        self,
        user: User,
        name: str,
        parent_id: str | None = None,
    ) -> FileItemResponse:
        """Create a new subfolder in Google Drive."""
        self._verify_drive_connected(user)
        storage = self._get_storage()

        target_parent = parent_id if parent_id else await storage.ensure_root(user)
        folder_id = await storage.create_folder(user, target_parent, name.strip())

        return FileItemResponse(
            id=folder_id,
            name=name.strip(),
            parent_id=target_parent,
            mime_type=FOLDER_MIME_TYPE,
            is_folder=True,
            size_bytes=0,
            md5=None,
        )

    async def rename_file(
        self,
        user: User,
        file_id: str,
        new_name: str,
    ) -> FileItemResponse:
        """Rename an existing file or folder in Google Drive."""
        self._verify_drive_connected(user)
        storage = self._get_storage()

        updated = await storage.rename(user, file_id, new_name.strip())
        return FileItemResponse(
            id=updated.id,
            name=updated.name,
            parent_id=updated.parent_id,
            mime_type=updated.mime_type,
            is_folder=updated.mime_type == FOLDER_MIME_TYPE,
            size_bytes=updated.size_bytes,
            md5=updated.md5,
        )

    async def move_file(
        self,
        user: User,
        file_id: str,
        new_parent_id: str,
    ) -> FileItemResponse:
        """Move a file or folder into a new parent folder."""
        self._verify_drive_connected(user)
        storage = self._get_storage()

        updated = await storage.move(user, file_id, new_parent_id)
        return FileItemResponse(
            id=updated.id,
            name=updated.name,
            parent_id=updated.parent_id,
            mime_type=updated.mime_type,
            is_folder=updated.mime_type == FOLDER_MIME_TYPE,
            size_bytes=updated.size_bytes,
            md5=updated.md5,
        )

    async def delete_file(
        self,
        user: User,
        file_id: str,
    ) -> None:
        """Permanently delete a file or folder from Google Drive."""
        self._verify_drive_connected(user)
        storage = self._get_storage()
        await storage.delete(user, file_id)
