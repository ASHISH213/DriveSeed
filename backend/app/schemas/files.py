"""Pydantic schemas for Google Drive library files, folders, and navigation."""

from pydantic import BaseModel, ConfigDict, Field


class BreadcrumbItem(BaseModel):
    """Breadcrumb node representing folder hierarchy from root."""

    id: str
    name: str


class FileItemResponse(BaseModel):
    """File or folder item in the library."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    parent_id: str
    mime_type: str
    is_folder: bool
    size_bytes: int = 0
    md5: str | None = None


class FileListResponse(BaseModel):
    """Response containing list of files in a folder and navigation breadcrumbs."""

    current_folder_id: str
    breadcrumbs: list[BreadcrumbItem] = Field(default_factory=list)
    files: list[FileItemResponse] = Field(default_factory=list)


class FilePatchRequest(BaseModel):
    """Payload to rename and/or move a file or folder."""

    name: str | None = Field(default=None, description="New name for the file or folder")
    parent_id: str | None = Field(default=None, description="New parent folder ID to move into")


class CreateFolderRequest(BaseModel):
    """Payload to create a new subfolder."""

    name: str = Field(..., description="Name of the new folder")
    parent_id: str | None = Field(
        default=None,
        description="Target parent folder ID. Defaults to user root folder if omitted.",
    )


class SubtitleTrackResponse(BaseModel):
    """Subtitle track metadata for media playback."""

    id: str
    name: str
    label: str
    language: str
    format: str


class SubtitleListResponse(BaseModel):
    """List of available subtitle tracks for a media file."""

    subtitles: list[SubtitleTrackResponse] = Field(default_factory=list)
