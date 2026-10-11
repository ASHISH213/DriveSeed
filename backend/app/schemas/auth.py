"""Pydantic schemas for authentication and user profile."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    """Authenticated user response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    created_at: datetime


class AuthUrlResponse(BaseModel):
    """Google OAuth initiation URL response."""

    url: str
