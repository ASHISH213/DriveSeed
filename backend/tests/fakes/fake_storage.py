"""In-memory fake implementation of StorageBackend for tests."""

import hashlib
import uuid
from collections.abc import AsyncIterator, Callable
from pathlib import Path

from app.interfaces.storage import StorageBackend
from app.interfaces.types import StorageQuota, StoredFile
from app.models.user import User


class FakeStorageBackend:
    """In-memory storage backend simulating Google Drive / local file operations."""

    def __init__(self) -> None:
        self.files: dict[str, StoredFile] = {}
        self.file_data: dict[str, bytes] = {}
        self.folders: dict[str, str] = {}  # folder_id -> folder_name
        self.user_roots: dict[str, str] = {}  # str(user.id) -> root_folder_id

    async def ensure_root(self, user: User) -> str:
        """Ensure the user's root folder exists and return its ID."""
        user_key = str(user.id)
        if user_key not in self.user_roots:
            root_id = f"root_{uuid.uuid4().hex[:8]}"
            self.user_roots[user_key] = root_id
            self.folders[root_id] = "DriveSeed"
        return self.user_roots[user_key]

    async def create_folder(self, user: User, parent_id: str, name: str) -> str:
        """Create a subfolder and return its ID."""
        folder_id = f"folder_{uuid.uuid4().hex[:8]}"
        self.folders[folder_id] = name
        return folder_id

    async def upload_file(
        self,
        user: User,
        parent_id: str,
        local_path: Path,
        on_progress: Callable[[int, int], None],
    ) -> StoredFile:
        """Upload a local file with progress tracking and MD5 verification."""
        content = local_path.read_bytes()
        file_size = len(content)
        md5_hash = hashlib.md5(content).hexdigest()

        # Simulate progress updates
        on_progress(file_size // 2, file_size)
        on_progress(file_size, file_size)

        file_id = f"file_{uuid.uuid4().hex[:8]}"
        stored = StoredFile(
            id=file_id,
            name=local_path.name,
            parent_id=parent_id,
            mime_type="application/octet-stream",
            size_bytes=file_size,
            md5=md5_hash,
        )
        self.files[file_id] = stored
        self.file_data[file_id] = content
        return stored

    async def list_folder(self, user: User, folder_id: str) -> list[StoredFile]:
        """List files directly inside the given folder."""
        return [f for f in self.files.values() if f.parent_id == folder_id]

    async def open_range(
        self,
        user: User,
        file_id: str,
        start: int,
        end: int | None,
    ) -> AsyncIterator[bytes]:
        """Stream bytes in the requested range."""
        if file_id not in self.file_data:
            raise FileNotFoundError(f"File {file_id} not found")

        data = self.file_data[file_id]
        end_idx = len(data) if end is None else end + 1
        sliced = data[start:end_idx]

        chunk_size = 64 * 1024
        for i in range(0, len(sliced), chunk_size):
            yield sliced[i : i + chunk_size]

    async def rename(self, user: User, file_id: str, new_name: str) -> StoredFile:
        """Rename an existing file."""
        if file_id not in self.files:
            raise FileNotFoundError(f"File {file_id} not found")
        stored = self.files[file_id]
        updated = StoredFile(
            id=stored.id,
            name=new_name,
            parent_id=stored.parent_id,
            mime_type=stored.mime_type,
            size_bytes=stored.size_bytes,
            md5=stored.md5,
        )
        self.files[file_id] = updated
        return updated

    async def move(self, user: User, file_id: str, new_parent_id: str) -> StoredFile:
        """Move an existing file to a new parent folder."""
        if file_id not in self.files:
            raise FileNotFoundError(f"File {file_id} not found")
        stored = self.files[file_id]
        updated = StoredFile(
            id=stored.id,
            name=stored.name,
            parent_id=new_parent_id,
            mime_type=stored.mime_type,
            size_bytes=stored.size_bytes,
            md5=stored.md5,
        )
        self.files[file_id] = updated
        return updated

    async def delete(self, user: User, file_id: str) -> None:
        """Delete an existing file."""
        self.files.pop(file_id, None)
        self.file_data.pop(file_id, None)

    async def quota(self, user: User) -> StorageQuota:
        """Calculate storage quota usage."""
        used = sum(len(d) for d in self.file_data.values())
        total = 15 * 1024 * 1024 * 1024  # 15 GB default
        return StorageQuota(used_bytes=used, total_bytes=total)


# Type assertion for static protocol conformance
_conforms: StorageBackend = FakeStorageBackend()
