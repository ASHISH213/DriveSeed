"""Worker pipeline orchestrating download, Google Drive upload, verification, and cleanup."""

import logging
import shutil
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.models.task import Task
from app.models.task_file import TaskFile
from app.models.user import User
from app.services.drive import DriveApiStorage
from app.services.http_download import HttpEngine
from app.services.task_state import TaskState, TaskStateMachine

logger = logging.getLogger(__name__)


async def process_download_task(ctx: dict[str, Any], task_id: str) -> None:
    """Execute complete download -> upload -> verify -> cleanup lifecycle for a task."""
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        logger.error("Invalid task_id format: %s", task_id)
        return

    session_factory = ctx.get("db_session_factory") or get_session_factory()
    settings = ctx.get("settings") or get_settings()
    temp_base = Path(settings.TEMP_DOWNLOAD_DIR)
    task_dest = temp_base / str(task_uuid)

    async with session_factory() as db:
        # Load task with eager-loaded files
        stmt = select(Task).where(Task.id == task_uuid).options(selectinload(Task.files))
        res = await db.execute(stmt)
        task = res.scalars().first()

        if not task:
            logger.error("Task %s not found in database", task_id)
            return

        if task.state in (
            TaskState.COMPLETED.value,
            TaskState.CANCELLED.value,
            TaskState.FAILED.value,
        ):
            logger.info("Task %s already in terminal state %s, skipping", task_id, task.state)
            return

        user = await db.get(User, task.user_id)
        if not user:
            task.state = TaskState.FAILED.value
            task.error = "User not found"
            await db.commit()
            return

        if not user.drive_refresh_token_enc:
            task.state = TaskState.FAILED.value
            task.error = "Google Drive account is not connected"
            await db.commit()
            return

        # Ensure task is in downloading state
        if task.state == TaskState.QUEUED.value:
            TaskStateMachine.transition(task, TaskState.DOWNLOADING)
            await db.commit()
            await db.refresh(task)

        # Ensure temp destination directory exists
        task_dest.mkdir(parents=True, exist_ok=True)

        engine = ctx.get("download_engine") or HttpEngine(allow_local=settings.DEBUG)

        try:
            # 1. Fetch metadata if size or files are missing
            if not task.size_bytes or not task.files:
                metadata = await engine.fetch_metadata(task.source_uri)
                task.size_bytes = metadata.total_size_bytes
                if task.name in ("Direct Download", "Magnet Download"):
                    task.name = metadata.name

                if not task.files:
                    for f_meta in metadata.files:
                        tf = TaskFile(
                            task_id=task.id,
                            path=f_meta.path,
                            size_bytes=f_meta.size_bytes,
                            selected=True,
                            state="downloading",
                        )
                        db.add(tf)

                await db.commit()
                await db.refresh(task)

            # 2. Download files to local temp directory
            last_commit = time.monotonic()
            download_completed = False

            async for progress in engine.start(task=task, selected=[0], dest=task_dest):
                if progress.total_bytes > 0:
                    task.progress = min(1.0, progress.downloaded_bytes / progress.total_bytes)

                if progress.state == "completed":
                    download_completed = True
                    task.progress = 1.0
                elif progress.state == "cancelled":
                    TaskStateMachine.transition(task, TaskState.CANCELLED)
                    await db.commit()
                    shutil.rmtree(task_dest, ignore_errors=True)
                    return

                # Throttle progress commits to once every second or on complete
                now = time.monotonic()
                if now - last_commit >= 1.0 or download_completed:
                    await db.commit()
                    last_commit = now

            # Locate downloaded file
            target_filename = Path(task.name).name
            downloaded_file = task_dest / target_filename
            if not downloaded_file.exists():
                candidates = [f for f in task_dest.iterdir() if f.is_file()]
                if candidates:
                    downloaded_file = candidates[0]
                else:
                    raise FileNotFoundError(f"Downloaded file not found in {task_dest}")

            # 3. Upload to Google Drive
            TaskStateMachine.transition(task, TaskState.UPLOADING)
            await db.commit()
            await db.refresh(task)

            storage = ctx.get("storage_backend") or DriveApiStorage(settings=settings)

            # Ensure root folder in user's Drive
            root_folder_id = await storage.ensure_root(user)
            if user.drive_root_folder_id != root_folder_id:
                user.drive_root_folder_id = root_folder_id
                await db.commit()

            def _on_upload_progress(uploaded: int, total: int) -> None:
                pass

            stored_file = await storage.upload_file(
                user=user,
                parent_id=root_folder_id,
                local_path=downloaded_file,
                on_progress=_on_upload_progress,
            )

            # Update task file association
            for tf in task.files:
                tf.drive_file_id = stored_file.id
                tf.state = "completed"

            # 4. Cleanup & Complete
            # HARD RULE: Local temp files are always deleted after a verified upload to Drive.
            shutil.rmtree(task_dest, ignore_errors=True)

            TaskStateMachine.transition(task, TaskState.COMPLETED)
            task.progress = 1.0
            task.completed_at = datetime.now(UTC)
            task.error = None
            await db.commit()

        except Exception as err:
            logger.exception("Pipeline failed for task %s: %s", task_id, err)
            task.state = TaskState.FAILED.value
            task.error = str(err)
            await db.commit()
            # Ensure local temp directory is always deleted on failure
            shutil.rmtree(task_dest, ignore_errors=True)
