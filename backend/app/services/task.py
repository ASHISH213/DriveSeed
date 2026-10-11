"""Task management service for creating, listing, and transitioning tasks."""

import re
import urllib.parse
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.interfaces.queue import TaskQueue
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreateRequest
from app.services.events import EventBroadcaster, TaskEvent, get_event_broadcaster
from app.services.task_state import (
    TaskState,
    TaskStateMachine,
)


class TaskNotFoundError(Exception):
    """Exception raised when a task is not found."""

    def __init__(self, task_id: uuid.UUID) -> None:
        self.task_id = task_id
        super().__init__(f"Task with ID {task_id} was not found.")


class TaskService:
    """Service encapsulating task queries, mutations, and transitions."""

    def __init__(
        self,
        queue: TaskQueue | None = None,
        broadcaster: EventBroadcaster | None = None,
    ) -> None:
        self.queue = queue
        self._broadcaster = broadcaster

    @property
    def broadcaster(self) -> EventBroadcaster:
        """Get or lazily initialize the EventBroadcaster."""
        if self._broadcaster is None:
            self._broadcaster = get_event_broadcaster()
        return self._broadcaster

    async def _emit_event(self, task: Task) -> None:
        """Publish real-time task state update."""
        try:
            await self.broadcaster.publish(
                TaskEvent(
                    task_id=str(task.id),
                    user_id=str(task.user_id),
                    name=task.name,
                    state=task.state,
                    progress=task.progress or 0.0,
                    error=task.error,
                )
            )
        except Exception:
            pass

    @staticmethod
    def _parse_source(
        source_uri: str, custom_name: str | None = None
    ) -> tuple[str, str | None, str]:
        """Infer source_type, info_hash, and default name from URI."""
        cleaned = source_uri.strip()
        if cleaned.startswith("magnet:"):
            source_type = "magnet"
            info_hash = None
            name = custom_name or "Magnet Download"

            # Parse magnet params
            parsed = urllib.parse.urlparse(cleaned)
            query_params = urllib.parse.parse_qs(parsed.query)

            # Extract info hash from xt=urn:btih:...
            xt_list = query_params.get("xt", [])
            for xt in xt_list:
                match = re.search(r"urn:btih:([a-fA-F0-9]{40}|[a-zA-Z2-7]{32})", xt)
                if match:
                    info_hash = match.group(1).lower()
                    break

            # Extract display name from dn=...
            dn_list = query_params.get("dn", [])
            if dn_list and not custom_name:
                name = dn_list[0]

            return source_type, info_hash, name

        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            source_type = "url"
            parsed_url = urllib.parse.urlparse(cleaned)
            path_name = Path(parsed_url.path).name if hasattr(parsed_url, "path") else ""
            name = custom_name or (path_name if path_name else "Direct Download")
            return source_type, None, name

        raise ValueError("Invalid source URI: Must be a magnet link or HTTP(S) URL")

    async def create_task(
        self,
        db: AsyncSession,
        user: User,
        request: TaskCreateRequest,
    ) -> Task:
        """Create a new download task in QUEUED state."""
        source_type, info_hash, name = self._parse_source(
            source_uri=request.source_uri,
            custom_name=request.name,
        )

        task = Task(
            user_id=user.id,
            source_type=source_type,
            source_uri=request.source_uri.strip(),
            info_hash=info_hash,
            name=name,
            state=TaskState.QUEUED.value,
            progress=0.0,
            size_bytes=None,
            error=None,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        if self.queue:
            await self.queue.enqueue("process_download_task", task_id=str(task.id))

        await self._emit_event(task)
        return task

    async def list_tasks(
        self,
        db: AsyncSession,
        user: User,
    ) -> list[Task]:
        """List tasks belonging to user with eager-loaded files."""
        stmt = (
            select(Task)
            .where(Task.user_id == user.id)
            .options(selectinload(Task.files))
            .order_by(Task.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_task(
        self,
        db: AsyncSession,
        user: User,
        task_id: uuid.UUID,
    ) -> Task:
        """Retrieve single task by ID for user."""
        stmt = (
            select(Task)
            .where((Task.id == task_id) & (Task.user_id == user.id))
            .options(selectinload(Task.files))
        )
        result = await db.execute(stmt)
        task = result.scalars().first()
        if not task:
            raise TaskNotFoundError(task_id)
        return task

    async def pause_task(
        self,
        db: AsyncSession,
        user: User,
        task_id: uuid.UUID,
    ) -> Task:
        """Transition task to PAUSED."""
        task = await self.get_task(db, user, task_id)
        TaskStateMachine.transition(task, TaskState.PAUSED)
        await db.commit()
        await db.refresh(task)
        await self._emit_event(task)
        return task

    async def resume_task(
        self,
        db: AsyncSession,
        user: User,
        task_id: uuid.UUID,
    ) -> Task:
        """Transition task to DOWNLOADING."""
        task = await self.get_task(db, user, task_id)
        TaskStateMachine.transition(task, TaskState.DOWNLOADING)
        await db.commit()
        await db.refresh(task)
        await self._emit_event(task)
        return task

    async def cancel_task(
        self,
        db: AsyncSession,
        user: User,
        task_id: uuid.UUID,
    ) -> Task:
        """Transition task to CANCELLED."""
        task = await self.get_task(db, user, task_id)
        TaskStateMachine.transition(task, TaskState.CANCELLED)
        await db.commit()
        await db.refresh(task)
        await self._emit_event(task)
        return task
