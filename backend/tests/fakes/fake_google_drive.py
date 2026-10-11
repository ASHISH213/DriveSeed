"""Fake Google Drive API v3 client for testing DriveApiStorage."""

import hashlib
import uuid
from typing import Any


class FakeResumableUploadRequest:
    """Simulates a Google API resumable upload request with chunked progression."""

    class ResumableStatus:
        def __init__(self, progress: int, total_size: int) -> None:
            self.resumable_progress = progress
            self.total_size = total_size

    def __init__(
        self,
        fake_files_resource: "FakeFilesResource",
        body: dict[str, Any],
        media_body: Any,
        fields: str = "",
    ) -> None:
        self.fake_files_resource = fake_files_resource
        self.body = body
        self.media_body = media_body
        self.fields = fields

        self.file_size = media_body.size() if hasattr(media_body, "size") else 0
        self.chunk_size = getattr(media_body, "_chunksize", 1024 * 1024)
        self.current_progress = 0
        self.is_done = False

    def next_chunk(self) -> tuple[Any, dict[str, Any] | None]:
        if self.is_done:
            return None, self._create_final_file()

        self.current_progress = min(self.current_progress + self.chunk_size, self.file_size)
        status = self.ResumableStatus(self.current_progress, self.file_size)

        if self.current_progress >= self.file_size:
            self.is_done = True
            response = self._create_final_file()
            return status, response

        return status, None

    def _create_final_file(self) -> dict[str, Any]:
        file_id = f"gdrive_file_{uuid.uuid4().hex[:8]}"

        # Calculate MD5 from the media file
        file_path = getattr(self.media_body, "_filename", None)
        md5_checksum = ""
        if file_path:
            hasher = hashlib.md5()
            with open(file_path, "rb") as f:
                while chunk := f.read(64 * 1024):
                    hasher.update(chunk)
            md5_checksum = hasher.hexdigest()

        # If fake client is configured to simulate corruption
        if self.fake_files_resource.simulate_checksum_mismatch:
            md5_checksum = "corrupted_md5_hash_value"

        item = {
            "id": file_id,
            "name": self.body.get("name", "uploaded_file"),
            "size": str(self.file_size),
            "md5Checksum": md5_checksum,
            "mimeType": "application/octet-stream",
            "parents": self.body.get("parents", []),
            "trashed": False,
        }
        self.fake_files_resource.store[file_id] = item
        return item


class FakeFilesResource:
    """Simulates service.files() in Google Drive API v3."""

    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.deleted_ids: list[str] = []
        self.simulate_checksum_mismatch = False

    def get(self, fileId: str, fields: str = "") -> Any:
        class Request:
            def __init__(self, item: dict[str, Any]) -> None:
                self.item = item

            def execute(self) -> dict[str, Any]:
                return dict(self.item)

        if fileId not in self.store:
            raise Exception(f"File not found: {fileId}")
        return Request(self.store[fileId])

    def list(self, q: str = "", spaces: str = "drive", fields: str = "") -> Any:
        class Request:
            def __init__(self, items: list[dict[str, Any]]) -> None:
                self.items = items

            def execute(self) -> dict[str, Any]:
                return {"files": [dict(it) for it in self.items]}

        matching: list[dict[str, Any]] = []
        for item in self.store.values():
            if item.get("trashed", False):
                continue

            # Query: name = 'DriveSeed'
            if "name = 'DriveSeed'" in q:
                if item.get("name") == "DriveSeed":
                    matching.append(item)
            # Query: 'folder_id' in parents
            elif "in parents" in q:
                parent_target = q.split("'")[1]
                if parent_target in item.get("parents", []):
                    matching.append(item)
            else:
                matching.append(item)

        return Request(matching)

    def create(self, body: dict[str, Any], media_body: Any = None, fields: str = "") -> Any:
        if media_body is not None:
            return FakeResumableUploadRequest(self, body, media_body, fields)

        class Request:
            def __init__(self, resource: "FakeFilesResource", body: dict[str, Any]) -> None:
                self.resource = resource
                self.body = body

            def execute(self) -> dict[str, Any]:
                file_id = f"folder_{uuid.uuid4().hex[:8]}"
                item = {
                    "id": file_id,
                    "name": self.body.get("name", "new_folder"),
                    "mimeType": self.body.get("mimeType", "application/vnd.google-apps.folder"),
                    "parents": self.body.get("parents", []),
                    "trashed": False,
                }
                self.resource.store[file_id] = item
                return item

        return Request(self, body)

    def update(
        self,
        fileId: str,
        body: dict[str, Any] | None = None,
        addParents: str | None = None,
        removeParents: str | None = None,
        fields: str = "",
    ) -> Any:
        class Request:
            def __init__(self, resource: "FakeFilesResource") -> None:
                self.resource = resource

            def execute(self) -> dict[str, Any]:
                item = self.resource.store[fileId]
                if body and "name" in body:
                    item["name"] = body["name"]
                if addParents:
                    item["parents"] = [addParents]
                return dict(item)

        if fileId not in self.store:
            raise Exception(f"File not found: {fileId}")
        return Request(self)

    def delete(self, fileId: str) -> Any:
        class Request:
            def __init__(self, resource: "FakeFilesResource") -> None:
                self.resource = resource

            def execute(self) -> dict[str, Any]:
                self.resource.deleted_ids.append(fileId)
                self.resource.store.pop(fileId, None)
                return {}

        return Request(self)

    def get_media(self, fileId: str) -> Any:
        class Request:
            def __init__(self, headers: dict[str, str]) -> None:
                self.headers = headers

            def execute(self) -> bytes:
                # Returns dummy payload respecting range
                return b"fake_media_bytes_data"

        return Request({})


class FakeAboutResource:
    """Simulates service.about() in Google Drive API v3."""

    def __init__(self) -> None:
        self.usage = 1024 * 1024 * 500  # 500 MB
        self.limit = 15 * 1024 * 1024 * 1024  # 15 GB

    def get(self, fields: str = "storageQuota") -> Any:
        class Request:
            def __init__(self, usage: int, limit: int) -> None:
                self.usage = usage
                self.limit = limit

            def execute(self) -> dict[str, Any]:
                return {
                    "storageQuota": {
                        "usage": str(self.usage),
                        "limit": str(self.limit),
                    }
                }

        return Request(self.usage, self.limit)


class FakeGoogleDriveService:
    """Mock Google Drive API v3 service."""

    def __init__(self) -> None:
        self._files = FakeFilesResource()
        self._about = FakeAboutResource()

    def files(self) -> FakeFilesResource:
        return self._files

    def about(self) -> FakeAboutResource:
        return self._about
