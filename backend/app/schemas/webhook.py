"""Pydantic schemas for webhook endpoints and event payloads."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WebhookEndpointCreate(BaseModel):
    """Payload to register a new webhook endpoint."""

    url: str = Field(..., max_length=1024, description="Target webhook URL (HTTP/HTTPS)")
    secret: str | None = Field(
        default=None,
        max_length=255,
        description="Shared HMAC secret (auto-generated with whsec_ prefix if omitted)",
    )
    events: list[str] | None = Field(
        default=None,
        description="List of subscribed event names (e.g. ['task.completed', 'task.failed'])",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        url_str = v.strip()
        if not (url_str.startswith("http://") or url_str.startswith("https://")):
            raise ValueError("Webhook URL must start with http:// or https://")
        return url_str


class WebhookEndpointResponse(BaseModel):
    """Webhook endpoint representation for users."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    secret: str
    events: list[str]
    is_active: bool
    created_at: datetime


class WebhookTestResponse(BaseModel):
    """Result of a test ping sent to a webhook endpoint."""

    success: bool
    status_code: int | None = None
    message: str
