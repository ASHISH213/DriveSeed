"""Files API router handling library browsing, search, rename, move, and delete."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.auth import get_current_user
from app.models.user import User
from app.schemas.files import (
    CreateFolderRequest,
    FileItemResponse,
    FileListResponse,
    FilePatchRequest,
    SubtitleListResponse,
)
from app.services.library import DriveNotConnectedError, LibraryService
from app.services.subtitles import SubtitleService

router = APIRouter(prefix="/api/files", tags=["Library"])


def get_library_service() -> LibraryService:
    """Dependency provider returning LibraryService instance."""
    return LibraryService()


@router.get("", response_model=FileListResponse)
async def list_files(
    current_user: Annotated[User, Depends(get_current_user)],
    library_service: Annotated[LibraryService, Depends(get_library_service)],
    folder: str | None = Query(default=None, description="Parent folder ID to list files from"),
    search: str | None = Query(default=None, description="Optional search term to filter by name"),
) -> FileListResponse:
    """List library files and subfolders with optional search filtering."""
    try:
        return await library_service.list_files(
            user=current_user,
            folder_id=folder,
            search=search,
        )
    except DriveNotConnectedError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "drive_not_connected", "message": str(err)}},
        ) from err


@router.post("/folder", response_model=FileItemResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    request: CreateFolderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    library_service: Annotated[LibraryService, Depends(get_library_service)],
) -> FileItemResponse:
    """Create a new subfolder in the library."""
    try:
        return await library_service.create_folder(
            user=current_user,
            name=request.name,
            parent_id=request.parent_id,
        )
    except DriveNotConnectedError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "drive_not_connected", "message": str(err)}},
        ) from err


@router.patch("/{file_id}", response_model=FileItemResponse)
async def update_file(
    file_id: str,
    request: FilePatchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    library_service: Annotated[LibraryService, Depends(get_library_service)],
) -> FileItemResponse:
    """Rename or move a library file or folder."""
    if not request.name and not request.parent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_request", "message": "Specify name or parent_id"}},
        )

    try:
        res: FileItemResponse | None = None
        if request.name:
            res = await library_service.rename_file(
                user=current_user,
                file_id=file_id,
                new_name=request.name,
            )
        if request.parent_id:
            res = await library_service.move_file(
                user=current_user,
                file_id=file_id,
                new_parent_id=request.parent_id,
            )
        assert res is not None
        return res
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "file_not_found", "message": f"File {file_id} not found"}},
        ) from err
    except DriveNotConnectedError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "drive_not_connected", "message": str(err)}},
        ) from err


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    library_service: Annotated[LibraryService, Depends(get_library_service)],
) -> None:
    """Delete a library file or folder from Google Drive."""
    try:
        await library_service.delete_file(user=current_user, file_id=file_id)
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "file_not_found", "message": f"File {file_id} not found"}},
        ) from err
    except DriveNotConnectedError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "drive_not_connected", "message": str(err)}},
        ) from err


def get_subtitle_service() -> SubtitleService:
    """Dependency provider returning SubtitleService instance."""
    return SubtitleService()


@router.get("/{file_id}/subtitles", response_model=SubtitleListResponse)
async def list_file_subtitles(
    file_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    subtitle_service: Annotated[SubtitleService, Depends(get_subtitle_service)],
) -> SubtitleListResponse:
    """List available sidecar subtitle tracks for a media file."""
    try:
        return await subtitle_service.list_subtitles(user=current_user, file_id=file_id)
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "file_not_found", "message": f"File {file_id} not found"}},
        ) from err
    except DriveNotConnectedError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "drive_not_connected", "message": str(err)}},
        ) from err


@router.get("/{file_id}/subtitles/{sub_id}")
async def get_subtitle_track(
    file_id: str,
    sub_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    subtitle_service: Annotated[SubtitleService, Depends(get_subtitle_service)],
) -> Response:
    """Retrieve and serve a subtitle track converted on the fly to WebVTT."""
    try:
        vtt_content = await subtitle_service.get_subtitle_content(
            user=current_user, file_id=file_id, sub_id=sub_id
        )
        return Response(
            content=vtt_content,
            media_type="text/vtt; charset=utf-8",
            headers={
                "Content-Type": "text/vtt; charset=utf-8",
                "Cache-Control": "private, max-age=3600",
            },
        )
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "file_not_found",
                    "message": f"Subtitle file {sub_id} not found",
                }
            },
        ) from err
    except DriveNotConnectedError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "drive_not_connected", "message": str(err)}},
        ) from err
