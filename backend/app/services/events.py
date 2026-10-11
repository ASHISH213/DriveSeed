"""Real-time event broadcasting service via Redis pub/sub."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


class TaskEvent(BaseModel):
    """Payload representing a real-time task lifecycle or progress update."""

    task_id: str
    user_id: str
    state: str
    name: str | None = None
    progress: float = 0.0
    speed_bps: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    error: str | None = None
    timestamp: float = Field(default_factory=time.time)


class EventBroadcaster:
    """Manages publishing and subscribing to real-time events over Redis pub/sub."""

    def __init__(self, redis_client: Any = None) -> None:
        self._redis_client = redis_client

    def _get_client(self) -> Any:
        return self._redis_client if self._redis_client is not None else get_redis_client()

    @staticmethod
    def get_channel(user_id: str) -> str:
        """Return Redis channel name for a specific user."""
        return f"driveseed:events:{user_id}"

    async def publish(self, event: TaskEvent) -> None:
        """Publish an event to the user-scoped Redis channel."""
        try:
            client = self._get_client()
            channel = self.get_channel(event.user_id)
            message = event.model_dump_json()
            await client.publish(channel, message)
        except Exception as err:
            logger.warning("Failed to publish event for user %s: %s", event.user_id, err)

    async def subscribe(
        self,
        user_id: str,
        request: Any = None,
        heartbeat_interval: float = 15.0,
        max_events: int | None = None,
    ) -> AsyncIterator[str]:
        """Subscribe to user's event stream yielding SSE formatted chunks with ping heartbeats."""
        client = self._get_client()
        pubsub = client.pubsub()
        channel = self.get_channel(user_id)

        await pubsub.subscribe(channel)
        yielded_count = 0
        try:
            # Yield initial connection confirmation comment
            yield ": connected\n\n"
            yielded_count += 1
            if max_events is not None and yielded_count >= max_events:
                return

            last_ping = time.monotonic()

            while True:
                if request is not None and hasattr(request, "is_disconnected"):
                    if await request.is_disconnected():
                        break

                try:
                    # Poll for next message with a short timeout
                    msg = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                        timeout=1.0,
                    )
                    now = time.monotonic()
                    if msg and msg.get("type") == "message":
                        data_str = msg.get("data")
                        if isinstance(data_str, bytes):
                            data_str = data_str.decode("utf-8")
                        yield f"event: task_update\ndata: {data_str}\n\n"
                        yielded_count += 1
                        last_ping = now
                        if max_events is not None and yielded_count >= max_events:
                            return
                    elif now - last_ping >= heartbeat_interval:
                        yield ": ping\n\n"
                        yielded_count += 1
                        last_ping = now
                        if max_events is not None and yielded_count >= max_events:
                            return
                except TimeoutError:
                    now = time.monotonic()
                    if now - last_ping >= heartbeat_interval:
                        yield ": ping\n\n"
                        yielded_count += 1
                        last_ping = now
                        if max_events is not None and yielded_count >= max_events:
                            return
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except Exception:
                pass


# Global singleton instance
_broadcaster: EventBroadcaster | None = None


def get_event_broadcaster() -> EventBroadcaster:
    """Dependency provider returning singleton EventBroadcaster."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = EventBroadcaster()
    return _broadcaster


def set_event_broadcaster(broadcaster: EventBroadcaster | None) -> None:
    """Override or reset the singleton EventBroadcaster (useful for tests)."""
    global _broadcaster
    _broadcaster = broadcaster
