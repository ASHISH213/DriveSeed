"""Pydantic schemas for personal API tokens."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiTokenCreateRequest(BaseModel):
    """Request payload to create a new personal API token."""

    label: str = Field(..., min_length=1, max_length=255, description="Token descriptive label")


class ApiTokenResponse(BaseModel):
    """API token metadata response (never reveals raw token or hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prefix: str
    label: str
    created_at: datetime
    last_used_at: datetime | None = None


class ApiTokenCreatedResponse(ApiTokenResponse):
    """Response returned only once upon token generation, exposing the raw secret."""

    token: str = Field(..., description="Raw personal access token (one-time reveal)")
