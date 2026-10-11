"""In-memory fake AsyncSession for testing database interactions without Postgres."""

import uuid
from typing import Any

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


class FakeAsyncSession:
    """In-memory fake AsyncSession for testing services and routers."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}
        self.added: list[Any] = []

    def add(self, instance: Any) -> None:
        self.added.append(instance)
        if isinstance(instance, User):
            if instance.id is None:
                instance.id = uuid.uuid4()
            self.users[instance.id] = instance

    async def commit(self) -> None:
        pass

    async def refresh(self, instance: Any) -> None:
        pass

    async def execute(self, statement: Any) -> FakeExecuteResult:
        matching: list[Any] = []
        try:
            params = statement.compile().params
            for u in self.users.values():
                id_match = any(v == u.id for v in params.values() if isinstance(v, uuid.UUID))
                sub_match = any(v == u.google_sub for v in params.values() if isinstance(v, str))
                email_match = any(v == u.email for v in params.values() if isinstance(v, str))
                if id_match or sub_match or email_match:
                    matching.append(u)
        except Exception:
            # Fallback if no params or non-compilable
            pass

        return FakeExecuteResult(matching)

    async def get(self, entity_class: type, ident: Any) -> Any | None:
        if entity_class is User and isinstance(ident, uuid.UUID):
            return self.users.get(ident)
        return None
