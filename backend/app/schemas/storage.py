"""Pydantic schemas for storage quota metrics."""

from pydantic import BaseModel, Field


class StorageResponse(BaseModel):
    """Google Drive storage quota metrics."""

    used_bytes: int = Field(..., ge=0, description="Bytes currently consumed in Google Drive")
    total_bytes: int = Field(..., ge=0, description="Total storage capacity in bytes")
    free_bytes: int = Field(..., ge=0, description="Remaining free space in bytes")
    percent_used: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of storage used (0.0 - 100.0)",
    )
