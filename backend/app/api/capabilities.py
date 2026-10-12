"""API router exposing runtime capabilities and feature flags."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.capabilities import CapabilitiesResponse, FeatureFlags, RuntimeLimits

router = APIRouter(prefix="/api/capabilities", tags=["Capabilities"])


@router.get("", response_model=CapabilitiesResponse)
async def get_capabilities(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CapabilitiesResponse:
    """Return runtime profile, storage backend type, limits, and feature flags."""
    is_colab = settings.PROFILE == "colab"

    if is_colab:
        features = FeatureFlags(
            torrent=False,
            direct_download=True,
            streaming=False,
            transcoding=False,
            rss=False,
            telegram=False,
            webhooks=False,
            multi_user=False,
        )
        storage_backend = "mounted"
    else:
        features = FeatureFlags(
            torrent=True,
            direct_download=True,
            streaming=True,
            transcoding=True,
            rss=True,
            telegram=bool(settings.TELEGRAM_BOT_TOKEN),
            webhooks=True,
            multi_user=True,
        )
        storage_backend = "drive_api"

    limits = RuntimeLimits(
        max_active_tasks=settings.MAX_ACTIVE_TASKS_PER_USER,
    )

    return CapabilitiesResponse(
        profile=settings.PROFILE,
        storage_backend=storage_backend,
        features=features,
        limits=limits,
    )
