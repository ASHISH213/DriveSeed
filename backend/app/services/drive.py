"""Google Drive API v3 storage backend implementation."""

import asyncio
import hashlib
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.core.config import Settings, get_settings
from app.core.security import decrypt_token
from app.interfaces.types import StorageQuota, StoredFile
from app.models.user import User

FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB (must be multiple of 256 KB)


class StorageError(Exception):
    """Domain exception for storage backend operations."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def calculate_file_md5(file_path: Path) -> str:
    """Compute MD5 hex digest of a local file in chunks."""
    hasher = hashlib.md5()
    with file_path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


class DriveApiStorage:
    """Production StorageBackend using Google Drive API v3."""

    def __init__(
        self,
        settings: Settings | None = None,
        client_factory: Callable[[User], Any] | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        self.settings = settings or get_settings()
        self._client_factory = client_factory
        self.chunk_size = chunk_size

    def _get_service(self, user: User) -> Any:
        """Obtain an authenticated Google Drive API service resource."""
        if self._client_factory:
            return self._client_factory(user)

        if not user.drive_refresh_token_enc:
            raise StorageError(
                code="no_drive_token",
                message="User does not have an authorized Google Drive refresh token",
            )

        refresh_token = decrypt_token(user.drive_refresh_token_enc)
        creds = Credentials(  # type: ignore[no-untyped-call]
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.settings.GOOGLE_CLIENT_ID,
            client_secret=self.settings.GOOGLE_CLIENT_SECRET,
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    async def ensure_root(self, user: User) -> str:
        """Find or create the 'DriveSeed' root folder in user's Drive."""
        service = self._get_service(user)

        def _sync_ensure_root() -> str:
            # Check cached root id first
            if user.drive_root_folder_id:
                try:
                    res = (
                        service.files()
                        .get(
                            fileId=user.drive_root_folder_id,
                            fields="id, trashed",
                        )
                        .execute()
                    )
                    if not res.get("trashed", False):
                        return str(res["id"])
                except Exception:
                    pass

            # Search by name in Drive
            query = f"name = 'DriveSeed' and mimeType = '{FOLDER_MIME_TYPE}' and trashed = false"
            results = (
                service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name)",
                )
                .execute()
            )
            files = results.get("files", [])
            if files:
                return str(files[0]["id"])

            # Create root folder
            body = {
                "name": "DriveSeed",
                "mimeType": FOLDER_MIME_TYPE,
            }
            created = service.files().create(body=body, fields="id").execute()
            return str(created["id"])

        return await asyncio.to_thread(_sync_ensure_root)

    async def create_folder(self, user: User, parent_id: str, name: str) -> str:
        """Create a folder inside a parent folder."""
        service = self._get_service(user)

        def _sync_create() -> str:
            body = {
                "name": name,
                "mimeType": FOLDER_MIME_TYPE,
                "parents": [parent_id],
            }
            res = service.files().create(body=body, fields="id").execute()
            return str(res["id"])

        return await asyncio.to_thread(_sync_create)

    async def upload_file(
        self,
        user: User,
        parent_id: str,
        local_path: Path,
        on_progress: Callable[[int, int], None],
    ) -> StoredFile:
        """Upload local file with resumable chunked upload and size/MD5 verification."""
        service = self._get_service(user)
        file_size = local_path.stat().st_size
        local_md5 = calculate_file_md5(local_path)

        def _sync_upload() -> StoredFile:
            media = MediaFileUpload(
                str(local_path),
                resumable=True,
                chunksize=self.chunk_size,
            )
            body = {
                "name": local_path.name,
                "parents": [parent_id],
            }
            request = service.files().create(
                body=body,
                media_body=media,
                fields="id, name, size, md5Checksum, mimeType, parents",
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    on_progress(status.resumable_progress, file_size)

            on_progress(file_size, file_size)

            remote_id = response["id"]
            remote_size = int(response.get("size", 0))
            remote_md5 = response.get("md5Checksum", "")

            # Integrity verification
            if remote_size != file_size or remote_md5 != local_md5:
                # Delete corrupted file on mismatch
                try:
                    service.files().delete(fileId=remote_id).execute()
                except Exception:
                    pass
                raise StorageError(
                    code="checksum_mismatch",
                    message=(
                        f"Integrity check failed: local size {file_size} vs remote {remote_size}, "
                        f"local MD5 {local_md5} vs remote {remote_md5}"
                    ),
                )

            return StoredFile(
                id=remote_id,
                name=response.get("name", local_path.name),
                parent_id=parent_id,
                mime_type=response.get("mimeType", "application/octet-stream"),
                size_bytes=remote_size,
                md5=remote_md5,
            )

        return await asyncio.to_thread(_sync_upload)

    async def list_folder(self, user: User, folder_id: str) -> list[StoredFile]:
        """List files and folders directly inside folder_id."""
        service = self._get_service(user)

        def _sync_list() -> list[StoredFile]:
            query = f"'{folder_id}' in parents and trashed = false"
            results = (
                service.files()
                .list(
                    q=query,
                    fields="files(id, name, mimeType, size, md5Checksum, parents)",
                )
                .execute()
            )
            files = results.get("files", [])
            output: list[StoredFile] = []
            for f in files:
                output.append(
                    StoredFile(
                        id=f["id"],
                        name=f["name"],
                        parent_id=folder_id,
                        mime_type=f.get("mimeType", "application/octet-stream"),
                        size_bytes=int(f.get("size", 0)),
                        md5=f.get("md5Checksum"),
                    )
                )
            return output

        return await asyncio.to_thread(_sync_list)

    async def open_range(
        self,
        user: User,
        file_id: str,
        start: int,
        end: int | None,
    ) -> AsyncIterator[bytes]:
        """Stream a byte range from Google Drive."""
        service = self._get_service(user)

        def _sync_fetch_range() -> bytes:
            request = service.files().get_media(fileId=file_id)
            range_header = f"bytes={start}-{end if end is not None else ''}"
            request.headers["Range"] = range_header
            return request.execute()  # type: ignore[no-any-return]

        data = await asyncio.to_thread(_sync_fetch_range)
        yield data

    async def rename(self, user: User, file_id: str, new_name: str) -> StoredFile:
        """Rename an existing file or folder in Google Drive."""
        service = self._get_service(user)

        def _sync_rename() -> StoredFile:
            res = (
                service.files()
                .update(
                    fileId=file_id,
                    body={"name": new_name},
                    fields="id, name, mimeType, size, md5Checksum, parents",
                )
                .execute()
            )
            parents = res.get("parents", [""])
            return StoredFile(
                id=res["id"],
                name=res["name"],
                parent_id=parents[0] if parents else "",
                mime_type=res.get("mimeType", "application/octet-stream"),
                size_bytes=int(res.get("size", 0)),
                md5=res.get("md5Checksum"),
            )

        return await asyncio.to_thread(_sync_rename)

    async def move(self, user: User, file_id: str, new_parent_id: str) -> StoredFile:
        """Move a file to a new parent folder."""
        service = self._get_service(user)

        def _sync_move() -> StoredFile:
            # First fetch existing parents
            file_meta = service.files().get(fileId=file_id, fields="parents").execute()
            old_parents = ",".join(file_meta.get("parents", []))

            res = (
                service.files()
                .update(
                    fileId=file_id,
                    addParents=new_parent_id,
                    removeParents=old_parents,
                    fields="id, name, mimeType, size, md5Checksum, parents",
                )
                .execute()
            )
            return StoredFile(
                id=res["id"],
                name=res["name"],
                parent_id=new_parent_id,
                mime_type=res.get("mimeType", "application/octet-stream"),
                size_bytes=int(res.get("size", 0)),
                md5=res.get("md5Checksum"),
            )

        return await asyncio.to_thread(_sync_move)

    async def delete(self, user: User, file_id: str) -> None:
        """Permanently delete a file or folder from Google Drive."""
        service = self._get_service(user)

        def _sync_delete() -> None:
            service.files().delete(fileId=file_id).execute()

        await asyncio.to_thread(_sync_delete)

    async def quota(self, user: User) -> StorageQuota:
        """Retrieve user's storage quota from Google Drive."""
        service = self._get_service(user)

        def _sync_quota() -> StorageQuota:
            about = service.about().get(fields="storageQuota").execute()
            quota_data = about.get("storageQuota", {})
            total = int(quota_data.get("limit", 15 * 1024 * 1024 * 1024))
            used = int(quota_data.get("usage", 0))
            return StorageQuota(
                used_bytes=used,
                total_bytes=total,
            )

        return await asyncio.to_thread(_sync_quota)
