"""Pydantic schemas for RSS subscriptions, feed previews, and sync responses."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RssSubscriptionCreate(BaseModel):
    """Payload to create an RSS feed subscription."""

    name: str = Field(..., min_length=1, max_length=255, description="Subscription label")
    url: str = Field(..., max_length=1024, description="Feed URL (HTTP/HTTPS)")
    filter_regex: str | None = Field(
        default=None,
        max_length=512,
        description="Optional regex to match item titles (e.g. (?i)Ubuntu.*amd64)",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        url_str = v.strip()
        if not (url_str.startswith("http://") or url_str.startswith("https://")):
            raise ValueError("Feed URL must start with http:// or https://")
        return url_str

    @field_validator("filter_regex")
    @classmethod
    def validate_regex(cls, v: str | None) -> str | None:
        if v is not None and v.strip():
            try:
                re.compile(v.strip())
            except re.error as err:
                raise ValueError(f"Invalid regular expression: {err}") from err
            return v.strip()
        return None


class RssSubscriptionResponse(BaseModel):
    """RSS Subscription response model."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    url: str
    filter_regex: str | None = None
    is_active: bool
    last_checked_at: datetime | None = None
    last_item_title: str | None = None
    created_at: datetime


class RssPreviewRequest(BaseModel):
    """Payload to preview an RSS feed without saving."""

    url: str = Field(..., max_length=1024)
    filter_regex: str | None = Field(default=None, max_length=512)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        url_str = v.strip()
        if not (url_str.startswith("http://") or url_str.startswith("https://")):
            raise ValueError("Feed URL must start with http:// or https://")
        return url_str


class RssFeedItemPreview(BaseModel):
    """Individual item extracted from an RSS feed."""

    title: str
    link: str
    is_match: bool


class RssPreviewResponse(BaseModel):
    """Result of previewing an RSS feed URL."""

    feed_title: str | None = None
    total_items: int
    matching_items: list[RssFeedItemPreview]


class RssSyncResponse(BaseModel):
    """Result of synchronizing an RSS subscription."""

    subscription_id: uuid.UUID
    items_checked: int
    tasks_created: int
    created_task_ids: list[uuid.UUID]
