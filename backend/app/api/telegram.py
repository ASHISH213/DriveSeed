"""Telegram Bot API router for webhooks, linking codes, and status."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.files import get_library_service
from app.api.tasks import get_task_service
from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.telegram import TelegramLinkCodeResponse, TelegramStatusResponse
from app.services.library import LibraryService
from app.services.task import TaskService
from app.services.telegram import TelegramBotService

router = APIRouter(prefix="/api/telegram", tags=["Telegram"])


def get_telegram_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> TelegramBotService:
    """Dependency provider returning TelegramBotService instance."""
    return TelegramBotService(settings=settings)


@router.post("/webhook")
async def telegram_webhook(
    update: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tg_service: Annotated[TelegramBotService, Depends(get_telegram_service)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
    library_service: Annotated[LibraryService, Depends(get_library_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_telegram_bot_api_secret_token: Annotated[
        str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")
    ] = None,
) -> dict[str, bool]:
    """Ingest updates from Telegram Bot webhook."""
    if settings.TELEGRAM_WEBHOOK_SECRET:
        if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid Telegram webhook secret token",
            )

    await tg_service.handle_update(
        db=db,
        update=update,
        task_service=task_service,
        library_service=library_service,
    )
    return {"ok": True}


@router.get("/status", response_model=TelegramStatusResponse)
async def get_telegram_status(
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TelegramStatusResponse:
    """Check whether current user account has an active linked Telegram chat ID."""
    return TelegramStatusResponse(
        is_linked=bool(current_user.telegram_chat_id),
        chat_id=current_user.telegram_chat_id,
        bot_username=settings.TELEGRAM_BOT_USERNAME or None,
    )


@router.post("/link-code", response_model=TelegramLinkCodeResponse)
async def generate_link_code(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tg_service: Annotated[TelegramBotService, Depends(get_telegram_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TelegramLinkCodeResponse:
    """Generate temporary 6-character link code and deep link for connecting Telegram account."""
    code, deep_link = await tg_service.generate_link_token(db=db, user_id=current_user.id)
    return TelegramLinkCodeResponse(
        code=code,
        bot_username=settings.TELEGRAM_BOT_USERNAME or None,
        deep_link=deep_link,
        expires_in_seconds=600,
    )


@router.delete("/link", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_telegram(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tg_service: Annotated[TelegramBotService, Depends(get_telegram_service)],
) -> Response:
    """Disconnect Telegram chat ID from current user."""
    await tg_service.unlink_chat(db=db, user_id=current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
