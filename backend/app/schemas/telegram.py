"""Pydantic schemas for Telegram Bot endpoints."""

from pydantic import BaseModel, ConfigDict


class TelegramStatusResponse(BaseModel):
    """Telegram connection status for current authenticated user."""

    is_linked: bool
    chat_id: str | None = None
    bot_username: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TelegramLinkCodeResponse(BaseModel):
    """Temporary link code and deep link for connecting Telegram account."""

    code: str
    bot_username: str | None = None
    deep_link: str | None = None
    expires_in_seconds: int = 600

    model_config = ConfigDict(from_attributes=True)
