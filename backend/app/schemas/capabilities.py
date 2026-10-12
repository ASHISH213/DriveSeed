"""Pydantic schemas for runtime capability inspection."""

from pydantic import BaseModel, Field


class FeatureFlags(BaseModel):
    torrent: bool = Field(..., description="Whether torrent/magnet downloading is enabled")
    direct_download: bool = Field(..., description="Whether direct HTTP(S) download is enabled")
    streaming: bool = Field(..., description="Whether in-app media proxy streaming is enabled")
    transcoding: bool = Field(..., description="Whether on-demand FFmpeg transcoding is enabled")
    rss: bool = Field(..., description="Whether RSS auto-downloading is enabled")
    telegram: bool = Field(..., description="Whether Telegram notifications and bot are enabled")
    webhooks: bool = Field(..., description="Whether webhook event dispatches are enabled")
    multi_user: bool = Field(..., description="Whether multi-user authentication is supported")


class RuntimeLimits(BaseModel):
    max_active_tasks: int = Field(..., description="Maximum active concurrent downloads per user")


class CapabilitiesResponse(BaseModel):
    profile: str = Field(..., description="Active runtime profile ('server' or 'colab')")
    storage_backend: str = Field(
        ..., description="Active storage backend type ('drive_api' or 'mounted')"
    )
    features: FeatureFlags = Field(..., description="Enabled/disabled feature set")
    limits: RuntimeLimits = Field(..., description="Configured operational limits")
