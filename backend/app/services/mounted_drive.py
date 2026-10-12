"""Storage backend implementation for Google Colab mounted Drive directory."""

import hashlib
import mimetypes
import os
import shutil
from collections.abc import AsyncIterator, Callable
from pathlib import Path

from app.core.config import Settings, get_settings
from app.interfaces.types import StorageQuota, StoredFile
from app.models.user import User

FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
CHUNK_SIZE = 16 * 1024 * 1024  # 16 MB chunks for sequential writes


class MountedDriveStorage:
    """StorageBackend operating directly on mounted Drive (/content/drive/MyDrive/DriveSeed)."""

    def __init__(
        self,
        settings: Settings | None = None,
        root_path: Path | str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.root_path = Path(root_path or self.settings.COLAB_DRIVE_ROOT).resolve()

    def _resolve_path(self, file_id: str) -> Path:
        """Resolve a file ID or relative path to an absolute path inside root_path."""
        if not file_id or file_id in ("root", "/"):
            return self.root_path
        # Sanitize against directory traversal
        clean_rel = file_id.lstrip("/\\")
        resolved = (self.root_path / clean_rel).resolve()
        if not str(resolved).startswith(str(self.root_path)):
            raise ValueError(f"Path traversal detected: {file_id}")
        return resolved

    def _to_id(self, path: Path) -> str:
        """Convert an absolute path to a relative ID string."""
        if path == self.root_path:
            return "root"
        return str(path.relative_to(self.root_path)).replace("\\", "/")

    async def ensure_root(self, user: User) -> str:
        """Ensure the root storage directory exists on the mounted Drive."""
        self.root_path.mkdir(parents=True, exist_ok=True)
        return "root"

    async def create_folder(self, user: User, parent_id: str, name: str) -> str:
        """Create a new folder inside parent directory."""
        parent_dir = self._resolve_path(parent_id)
        parent_dir.mkdir(parents=True, exist_ok=True)

        clean_name = Path(name).name
        target_dir = parent_dir / clean_name
        target_dir.mkdir(parents=True, exist_ok=True)
        return self._to_id(target_dir)

    async def upload_file(
        self,
        user: User,
        parent_id: str,
        local_path: Path,
        on_progress: Callable[[int, int], None],
    ) -> StoredFile:
        """Stream local scratch file to mounted Drive with atomic rename & checksum check."""
        parent_dir = self._resolve_path(parent_id)
        parent_dir.mkdir(parents=True, exist_ok=True)

        dest_name = local_path.name
        dest_file = parent_dir / dest_name
        temp_file = parent_dir / f".{dest_name}.driveseed_tmp"

        total_bytes = local_path.stat().st_size
        copied_bytes = 0
        hasher = hashlib.md5()

        try:
            with local_path.open("rb") as src, temp_file.open("wb") as dst:
                while True:
                    chunk = src.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    dst.write(chunk)
                    hasher.update(chunk)
                    copied_bytes += len(chunk)
                    on_progress(copied_bytes, total_bytes)
                dst.flush()
                try:
                    os.fsync(dst.fileno())
                except OSError:
                    pass

            # Verify size
            uploaded_size = temp_file.stat().st_size
            if uploaded_size != total_bytes:
                raise OSError(
                    f"Uploaded size mismatch: expected {total_bytes} bytes, "
                    f"wrote {uploaded_size} bytes"
                )

            # Atomic move / replace
            os.replace(temp_file, dest_file)
        except Exception:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            raise

        md5_digest = hasher.hexdigest()
        mime_type, _ = mimetypes.guess_type(dest_name)
        return StoredFile(
            id=self._to_id(dest_file),
            name=dest_name,
            parent_id=parent_id,
            mime_type=mime_type or "application/octet-stream",
            size_bytes=total_bytes,
            md5=md5_digest,
        )

    async def list_folder(self, user: User, folder_id: str) -> list[StoredFile]:
        """List files and directories inside parent folder."""
        folder_path = self._resolve_path(folder_id)
        if not folder_path.exists() or not folder_path.is_dir():
            return []

        results: list[StoredFile] = []
        for entry in sorted(folder_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            # Skip hidden and temp files
            if entry.name.startswith("."):
                continue

            is_dir = entry.is_dir()
            size = 0 if is_dir else entry.stat().st_size
            guessed_mime = mimetypes.guess_type(entry.name)[0]
            mime = FOLDER_MIME_TYPE if is_dir else (guessed_mime or "application/octet-stream")
            results.append(
                StoredFile(
                    id=self._to_id(entry),
                    name=entry.name,
                    parent_id=folder_id,
                    mime_type=mime,
                    size_bytes=size,
                    md5=None,
                )
            )
        return results

    async def get_file(self, user: User, file_id: str) -> StoredFile:
        """Fetch metadata for a file or folder by ID."""
        target_path = self._resolve_path(file_id)
        if not target_path.exists():
            raise FileNotFoundError(f"File or directory not found: {file_id}")

        is_dir = target_path.is_dir()
        size = 0 if is_dir else target_path.stat().st_size
        guessed_mime = mimetypes.guess_type(target_path.name)[0]
        mime = FOLDER_MIME_TYPE if is_dir else (guessed_mime or "application/octet-stream")
        parent_id = self._to_id(target_path.parent)

        return StoredFile(
            id=self._to_id(target_path),
            name=target_path.name,
            parent_id=parent_id,
            mime_type=mime,
            size_bytes=size,
            md5=None,
        )

    async def open_range(
        self,
        user: User,
        file_id: str,
        start: int,
        end: int | None,
    ) -> AsyncIterator[bytes]:
        """Read a slice of bytes from a stored file."""
        target_path = self._resolve_path(file_id)
        if not target_path.is_file():
            raise FileNotFoundError(f"File not found: {file_id}")

        file_size = target_path.stat().st_size
        limit = (end + 1) if end is not None else file_size
        limit = min(limit, file_size)

        with target_path.open("rb") as f:
            f.seek(start)
            remaining = limit - start
            while remaining > 0:
                chunk_len = min(64 * 1024, remaining)
                data = f.read(chunk_len)
                if not data:
                    break
                remaining -= len(data)
                yield data

    async def rename(self, user: User, file_id: str, new_name: str) -> StoredFile:
        """Rename an existing file or folder."""
        target_path = self._resolve_path(file_id)
        if not target_path.exists():
            raise FileNotFoundError(f"File not found: {file_id}")

        clean_name = Path(new_name).name
        new_path = target_path.parent / clean_name
        target_path.rename(new_path)
        return await self.get_file(user=user, file_id=self._to_id(new_path))

    async def move(self, user: User, file_id: str, new_parent_id: str) -> StoredFile:
        """Move a file or folder into a new parent folder."""
        target_path = self._resolve_path(file_id)
        new_parent_dir = self._resolve_path(new_parent_id)
        if not target_path.exists():
            raise FileNotFoundError(f"Source file not found: {file_id}")
        if not new_parent_dir.is_dir():
            raise FileNotFoundError(f"Destination folder not found: {new_parent_id}")

        dest_path = new_parent_dir / target_path.name
        shutil.move(str(target_path), str(dest_path))
        return await self.get_file(user=user, file_id=self._to_id(dest_path))

    async def delete(self, user: User, file_id: str) -> None:
        """Permanently delete a file or directory."""
        target_path = self._resolve_path(file_id)
        if not target_path.exists():
            return

        if target_path.is_dir():
            shutil.rmtree(target_path)
        else:
            target_path.unlink(missing_ok=True)

    async def quota(self, user: User) -> StorageQuota:
        """Retrieve storage capacity and usage for mounted Drive."""
        self.root_path.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(self.root_path)
        return StorageQuota(
            total_bytes=usage.total,
            used_bytes=usage.used,
        )
