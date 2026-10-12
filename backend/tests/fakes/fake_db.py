"""In-memory fake AsyncSession for testing database interactions without Postgres."""

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.api_token import ApiToken
from app.models.playback import Playback
from app.models.task import Task
from app.models.task_file import TaskFile
from app.models.user import User


class FakeScalarResult:
    """Fake result returned by FakeAsyncSession.execute."""

    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def first(self) -> Any | None:
        return self._items[0] if self._items else None

    def all(self) -> list[Any]:
        return list(self._items)


class FakeExecuteResult:
    """Fake result returned by execute."""

    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self._items)

    def scalar_one_or_none(self) -> Any | None:
        return self._items[0] if self._items else None

    def scalar(self) -> Any | None:
        return self._items[0] if self._items else None


class FakeAsyncSession:
    """In-memory fake AsyncSession for testing services and routers."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}
        self.tasks: dict[uuid.UUID, Task] = {}
        self.playbacks: dict[tuple[uuid.UUID, str], Any] = {}
        self.api_tokens: dict[uuid.UUID, ApiToken] = {}
        self.added: list[Any] = []

    def add(self, instance: Any) -> None:
        self.added.append(instance)
        if isinstance(instance, User):
            if instance.id is None:
                instance.id = uuid.uuid4()
            self.users[instance.id] = instance
        elif isinstance(instance, Task):
            if instance.id is None:
                instance.id = uuid.uuid4()
            if getattr(instance, "created_at", None) is None:
                instance.created_at = datetime.now(UTC)
            if not hasattr(instance, "files") or instance.__dict__.get("files") is None:
                instance.files = []
            self.tasks[instance.id] = instance
        elif isinstance(instance, TaskFile):
            if instance.id is None:
                instance.id = uuid.uuid4()
            task = self.tasks.get(instance.task_id)
            if task is not None:
                if not hasattr(task, "files") or task.__dict__.get("files") is None:
                    task.files = []
                if instance not in task.files:
                    task.files.append(instance)
        elif isinstance(instance, ApiToken):
            if instance.id is None:
                instance.id = uuid.uuid4()
            if getattr(instance, "created_at", None) is None:
                instance.created_at = datetime.now(UTC)
            self.api_tokens[instance.id] = instance
        else:
            # Playback or generic
            user_id = getattr(instance, "user_id", None)
            file_id = getattr(instance, "file_id", None)
            if user_id is not None and file_id is not None:
                self.playbacks[(user_id, file_id)] = instance

    async def delete(self, instance: Any) -> None:
        if instance in self.added:
            self.added.remove(instance)
        if isinstance(instance, ApiToken):
            self.api_tokens.pop(instance.id, None)
        user_id = getattr(instance, "user_id", None)
        file_id = getattr(instance, "file_id", None)
        if user_id is not None and file_id is not None:
            self.playbacks.pop((user_id, file_id), None)

    async def commit(self) -> None:
        pass

    async def refresh(self, instance: Any) -> None:
        pass

    async def execute(self, statement: Any) -> FakeExecuteResult:
        matching: list[Any] = []
        try:
            entity = None
            if hasattr(statement, "column_descriptions") and statement.column_descriptions:
                entity = statement.column_descriptions[0].get("entity")

            params = statement.compile().params

            if entity is User:
                for u in self.users.values():
                    id_match = any(v == u.id for v in params.values() if isinstance(v, uuid.UUID))
                    sub_match = any(
                        v == u.google_sub for v in params.values() if isinstance(v, str)
                    )
                    email_match = any(v == u.email for v in params.values() if isinstance(v, str))
                    if id_match or sub_match or email_match:
                        matching.append(u)
            elif entity is Task:
                # Find task id and user id from params
                param_ids = [v for k, v in params.items() if "id" in k and isinstance(v, uuid.UUID)]
                param_user_ids = [
                    v for k, v in params.items() if "user_id" in k and isinstance(v, uuid.UUID)
                ]

                task_list = list(self.tasks.values())
                for t in task_list:
                    # If user_id is in params, must match
                    if param_user_ids and t.user_id not in param_user_ids:
                        continue
                    # If specific task id is in params, must match
                    if param_ids:
                        task_id_matches = [pid for pid in param_ids if pid not in param_user_ids]
                        if task_id_matches and t.id not in task_id_matches:
                            continue
                    # Ensure files attribute is initialized
                    if not hasattr(t, "files") or t.__dict__.get("files") is None:
                        t.files = []
                    matching.append(t)
                matching.sort(
                    key=lambda x: x.created_at or datetime.min.replace(tzinfo=UTC), reverse=True
                )
            elif entity is Playback:
                user_id_param = next((v for v in params.values() if isinstance(v, uuid.UUID)), None)
                file_id_param = next((v for v in params.values() if isinstance(v, str)), None)
                for (uid, fid), p in self.playbacks.items():
                    if user_id_param and uid != user_id_param:
                        continue
                    if file_id_param and fid != file_id_param:
                        continue
                    matching.append(p)
            elif entity is ApiToken:
                hash_param = next(
                    (v for v in params.values() if isinstance(v, str) and len(v) == 64), None
                )
                user_id_param = next(
                    (v for k, v in params.items() if "user_id" in k and isinstance(v, uuid.UUID)),
                    None,
                )
                id_param = next(
                    (
                        v
                        for k, v in params.items()
                        if "id" in k and "user_id" not in k and isinstance(v, uuid.UUID)
                    ),
                    None,
                )
                for tok in self.api_tokens.values():
                    if hash_param and tok.token_hash != hash_param:
                        continue
                    if user_id_param and tok.user_id != user_id_param:
                        continue
                    if id_param and tok.id != id_param:
                        continue
                    matching.append(tok)
                matching.sort(
                    key=lambda x: x.created_at or datetime.min.replace(tzinfo=UTC), reverse=True
                )
            else:
                # Fallback matching for backward compatibility
                for u in self.users.values():
                    id_match = any(v == u.id for v in params.values() if isinstance(v, uuid.UUID))
                    sub_match = any(
                        v == u.google_sub for v in params.values() if isinstance(v, str)
                    )
                    email_match = any(v == u.email for v in params.values() if isinstance(v, str))
                    if id_match or sub_match or email_match:
                        matching.append(u)
        except Exception:
            pass

        return FakeExecuteResult(matching)

    async def get(self, entity_class: type, ident: Any) -> Any | None:
        if entity_class is User and isinstance(ident, uuid.UUID):
            return self.users.get(ident)
        if entity_class is Task and isinstance(ident, uuid.UUID):
            return self.tasks.get(ident)
        if entity_class is ApiToken and isinstance(ident, uuid.UUID):
            return self.api_tokens.get(ident)
        return None
