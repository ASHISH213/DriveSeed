"""StorageBackend protocol definition."""

from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.interfaces.types import StorageQuota, StoredFile
from app.models.user import User


@runtime_checkable
class StorageBackend(Protocol):
    """Protocol for cloud/local storage operations."""

    async def ensure_root(self, user: User) -> str:
        """Ensure the user's root folder exists and return its ID."""
        ...

    async def create_folder(self, user: User, parent_id: str, name: str) -> str:
        """Create a subfolder and return its ID."""
        ...

    async def upload_file(
        self,
        user: User,
        parent_id: str,
        local_path: Path,
        on_progress: Callable[[int, int], None],
    ) -> StoredFile:
        """Upload a local file with progress callback, verifying size and checksum."""
        ...

    async def list_folder(self, user: User, folder_id: str) -> list[StoredFile]:
        """List files and folders directly inside parent folder."""
        ...

    async def get_file(self, user: User, file_id: str) -> StoredFile:
        """Fetch metadata for an individual stored file or folder."""
        ...

    async def open_range(
        self,
        user: User,
        file_id: str,
        start: int,
        end: int | None,
    ) -> AsyncIterator[bytes]:
        """Stream a byte range from a stored file."""
        yield b""

    async def rename(self, user: User, file_id: str, new_name: str) -> StoredFile:
        """Rename an existing file or folder."""
        ...

    async def move(self, user: User, file_id: str, new_parent_id: str) -> StoredFile:
        """Move a file or folder into a new parent folder."""
        ...

    async def delete(self, user: User, file_id: str) -> None:
        """Permanently delete a file or folder."""
        ...

    async def quota(self, user: User) -> StorageQuota:
        """Retrieve total and used storage quota for the user."""
        ...
