"""Telegram Bot service for account linking, chat commands, and download notifications."""

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.ssrf import SSRFError, validate_url
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreateRequest
from app.services.library import LibraryService
from app.services.task import MaxActiveTasksExceededError, TaskService

logger = logging.getLogger(__name__)


def format_bytes(bytes_count: int | None) -> str:
    """Format bytes count into human-readable string."""
    if not bytes_count or bytes_count <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_idx = 0
    val = float(bytes_count)
    while val >= 1024.0 and unit_idx < len(units) - 1:
        val /= 1024.0
        unit_idx += 1
    return f"{val:.1f} {units[unit_idx]}" if unit_idx > 0 else f"{int(val)} B"


class TelegramBotService:
    """Handles Telegram Bot API interactions, webhooks, commands, and alerts."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client

    async def _get_client(self) -> tuple[httpx.AsyncClient, bool]:
        """Return an HTTP client and a flag indicating whether to close it."""
        if self._client is not None:
            return self._client, False
        return httpx.AsyncClient(timeout=10.0), True

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
    ) -> bool:
        """Send an HTML-formatted message to a Telegram chat."""
        token = self.settings.TELEGRAM_BOT_TOKEN
        if not token:
            logger.debug("Telegram bot token not configured; skipping send_message")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        http_client, should_close = await self._get_client()
        try:
            resp = await http_client.post(url, json=payload)
            if not resp.is_success:
                logger.warning(
                    "Telegram sendMessage failed for chat %s: %s %s",
                    chat_id,
                    resp.status_code,
                    resp.text,
                )
                return False
            return True
        except Exception as err:
            logger.error("Error dispatching Telegram message to %s: %s", chat_id, err)
            return False
        finally:
            if should_close:
                await http_client.aclose()

    async def generate_link_token(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> tuple[str, str | None]:
        """Generate a short-lived link token for connecting user's Telegram chat."""
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        # 6-character uppercase alphanumeric code
        token = secrets.token_hex(3).upper()
        user.telegram_link_token = token
        user.telegram_link_token_expires_at = datetime.now(UTC) + timedelta(minutes=10)
        await db.commit()

        deep_link = None
        if self.settings.TELEGRAM_BOT_USERNAME:
            deep_link = f"https://t.me/{self.settings.TELEGRAM_BOT_USERNAME}?start={token}"

        return token, deep_link

    async def link_chat(
        self,
        db: AsyncSession,
        chat_id: str,
        link_token: str,
    ) -> tuple[bool, str]:
        """Verify link token and attach Telegram chat ID to matching user."""
        clean_token = link_token.strip().upper()
        stmt = select(User).where(User.telegram_link_token == clean_token)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            return (
                False,
                "⚠️ Invalid link code. Please generate a new code in DriveSeed Settings.",
            )

        now = datetime.now(UTC)
        if user.telegram_link_token_expires_at is None or user.telegram_link_token_expires_at < now:
            return (
                False,
                "⌛ Link code has expired. Please generate a new code in DriveSeed Settings.",
            )

        user.telegram_chat_id = str(chat_id)
        user.telegram_link_token = None
        user.telegram_link_token_expires_at = None
        await db.commit()

        logger.info("Successfully linked Telegram chat %s to user %s", chat_id, user.id)
        return (
            True,
            (
                f"🎉 <b>Account Linked!</b>\n\nConnected to <b>{user.email}</b>.\n"
                "You can now send magnet links or URLs directly to download them to Google Drive."
            ),
        )

    async def unlink_chat(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> bool:
        """Disconnect Telegram chat ID for user."""
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user or not user.telegram_chat_id:
            return False

        user.telegram_chat_id = None
        user.telegram_link_token = None
        user.telegram_link_token_expires_at = None
        await db.commit()
        return True

    async def get_user_by_chat_id(
        self,
        db: AsyncSession,
        chat_id: str,
    ) -> User | None:
        """Look up user by registered Telegram chat ID."""
        stmt = select(User).where(User.telegram_chat_id == str(chat_id))
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def handle_update(
        self,
        db: AsyncSession,
        update: dict[str, Any],
        task_service: TaskService,
        library_service: LibraryService | None = None,
    ) -> str | None:
        """Process incoming Telegram update and send response."""
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return None

        chat = msg.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        text = str(msg.get("text", "")).strip()

        if not chat_id or not text:
            return None

        reply_text = await self._process_text(
            db=db,
            chat_id=chat_id,
            text=text,
            task_service=task_service,
            library_service=library_service,
        )

        if reply_text:
            await self.send_message(chat_id=chat_id, text=reply_text)

        return reply_text

    async def _process_text(
        self,
        db: AsyncSession,
        chat_id: str,
        text: str,
        task_service: TaskService,
        library_service: LibraryService | None = None,
    ) -> str:
        """Parse text command or URI and return response text."""
        parts = text.split()
        cmd = parts[0].lower() if parts else ""

        # Command: /start or /start <token>
        if cmd == "/start":
            if len(parts) > 1:
                link_token = parts[1]
                _, reply = await self.link_chat(db=db, chat_id=chat_id, link_token=link_token)
                return reply

            user = await self.get_user_by_chat_id(db, chat_id)
            if user:
                return (
                    f"👋 Welcome back, <b>{user.email}</b>!\n\n"
                    "DriveSeed Bot is linked and ready.\n\n"
                    "<b>Available Commands:</b>\n"
                    "• <code>/add &lt;magnet|url&gt;</code> — Start download\n"
                    "• <code>/status</code> — View active tasks\n"
                    "• <code>/library</code> — Browse recent Google Drive files\n"
                    "• <code>/unlink</code> — Disconnect your Telegram chat\n"
                    "• <code>/help</code> — Show this help message\n\n"
                    "<i>Tip: You can also send a magnet link or URL directly!</i>"
                )
            return (
                "👋 <b>Welcome to DriveSeed Bot!</b>\n\n"
                "To link your DriveSeed account:\n"
                "1. Sign in to DriveSeed in your browser\n"
                "2. Go to <b>Settings</b> ➔ <b>Telegram Bot</b>\n"
                "3. Click <b>Connect Telegram</b> to get your link code\n"
                "4. Reply here with: <code>/start &lt;YOUR_CODE&gt;</code>"
            )

        # Command: /help
        if cmd == "/help":
            return (
                "🤖 <b>DriveSeed Bot Commands:</b>\n\n"
                "• <code>/add &lt;magnet|url&gt;</code> — Add & start a new download\n"
                "• <code>/status</code> — Check progress of active downloads\n"
                "• <code>/library</code> — View recent files in Google Drive\n"
                "• <code>/unlink</code> — Unlink your account from this chat\n\n"
                "<i>Paste any magnet link or direct URL into the chat to start downloading.</i>"
            )

        # Command: /unlink
        if cmd == "/unlink":
            user = await self.get_user_by_chat_id(db, chat_id)
            if not user:
                return "ℹ️ This chat is not currently linked to any DriveSeed account."
            await self.unlink_chat(db, user.id)
            return "👋 <b>Account Unlinked.</b> You will no longer receive notifications here."

        # Command: /status
        if cmd == "/status":
            user = await self.get_user_by_chat_id(db, chat_id)
            if not user:
                return "⚠️ Link your DriveSeed account first using <code>/start &lt;code&gt;</code>."

            tasks = await task_service.list_tasks(db=db, user=user)
            active_tasks = [t for t in tasks if t.state in ("downloading", "uploading", "pending")]

            if not active_tasks:
                return "📊 <b>Status:</b> No downloads currently running."

            lines = [f"📊 <b>Active Tasks ({len(active_tasks)}):</b>\n"]
            for t in active_tasks[:5]:
                prog = f"{t.progress:.1f}%" if t.progress is not None else "0.0%"
                lines.append(f"• <b>{t.name}</b>\n  State: <code>{t.state}</code> | {prog}")
            return "\n".join(lines)

        # Command: /library
        if cmd == "/library":
            user = await self.get_user_by_chat_id(db, chat_id)
            if not user:
                return "⚠️ Link your DriveSeed account first using <code>/start &lt;code&gt;</code>."

            lib_srv = library_service or LibraryService()
            try:
                file_list = await lib_srv.list_files(user=user)
                if not file_list.files:
                    return "📁 <b>Library:</b> Your Google Drive library folder is empty."

                lines = ["📁 <b>Recent Drive Files:</b>\n"]
                for f in file_list.files[:6]:
                    size_str = format_bytes(f.size_bytes)
                    lines.append(f"• <b>{f.name}</b> ({size_str})")
                return "\n".join(lines)
            except Exception as lib_err:
                return f"⚠️ Could not load library: {lib_err}"

        # Command: /add <uri> or direct magnet/url paste
        uri_target: str | None = None
        if cmd == "/add" and len(parts) > 1:
            uri_target = parts[1].strip()
        elif (
            text.startswith("magnet:?") or text.startswith("http://") or text.startswith("https://")
        ):
            uri_target = text.strip()

        if uri_target:
            user = await self.get_user_by_chat_id(db, chat_id)
            if not user:
                return (
                    "⚠️ Please link your DriveSeed account first!\n"
                    "Use <code>/start &lt;code&gt;</code> with the code from Settings."
                )

            # SSRF validation for HTTP/HTTPS
            if uri_target.startswith("http://") or uri_target.startswith("https://"):
                try:
                    await validate_url(uri_target, allow_local=self.settings.DEBUG)
                except SSRFError as ssrf_err:
                    return f"❌ <b>Blocked URL:</b> {ssrf_err}"

            # Task Creation
            try:
                task = await task_service.create_task(
                    db=db,
                    user=user,
                    request=TaskCreateRequest(source_uri=uri_target),
                )
                # Auto-start task if possible
                try:
                    task = await task_service.start_task(
                        db=db,
                        user=user,
                        task_id=task.id,
                    )
                except Exception as start_err:
                    logger.debug("Task created but auto-start deferred: %s", start_err)

                return (
                    f"🚀 <b>Task Created!</b>\n\n"
                    f"<b>Name:</b> {task.name}\n"
                    f"<b>State:</b> <code>{task.state}</code>\n"
                    f"<b>ID:</b> <code>{task.id}</code>\n\n"
                    f"Download started to your Google Drive. You will be notified when complete!"
                )
            except MaxActiveTasksExceededError as limit_err:
                return f"⚠️ <b>Task Limit Exceeded:</b> {limit_err}"
            except Exception as task_err:
                return f"❌ <b>Failed to create task:</b> {task_err}"

        # Unknown command fallback
        return (
            "❓ Unknown command. Send <code>/help</code> to see available commands, "
            "or send a magnet link or URL to start downloading."
        )

    async def send_task_notification(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        event_name: str,
        task: Task,
    ) -> bool:
        """Send automated push notification on task completion or failure."""
        if not self.settings.TELEGRAM_BOT_TOKEN:
            return False

        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user or not user.telegram_chat_id:
            return False

        if event_name == "task.completed":
            size_str = format_bytes(task.size_bytes)
            text = (
                f"✅ <b>Download Complete!</b>\n\n"
                f"<b>Name:</b> {task.name}\n"
                f"<b>Size:</b> {size_str}\n"
                f"<b>Destination:</b> Google Drive 🎉\n\n"
                f"Your file is ready to stream or download in DriveSeed."
            )
        elif event_name == "task.failed":
            err_msg = task.error or "Unknown error occurred"
            text = (
                f"❌ <b>Download Failed</b>\n\n<b>Name:</b> {task.name}\n<b>Reason:</b> {err_msg}"
            )
        else:
            return False

        return await self.send_message(chat_id=user.telegram_chat_id, text=text)
