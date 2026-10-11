"""In-memory Fake Redis client and pubsub for testing."""

import asyncio
from typing import Any


class FakePubSub:
    """In-memory pubsub subscriber."""

    def __init__(self, fake_redis: "FakeRedis") -> None:
        self.fake_redis = fake_redis
        self.channels: set[str] = set()
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.closed = False

    async def subscribe(self, *channels: str) -> None:
        """Subscribe to given channels."""
        for ch in channels:
            self.channels.add(ch)
            if ch not in self.fake_redis.subscribers:
                self.fake_redis.subscribers[ch] = []
            if self not in self.fake_redis.subscribers[ch]:
                self.fake_redis.subscribers[ch].append(self)

    async def unsubscribe(self, *channels: str) -> None:
        """Unsubscribe from channels or all subscribed channels if none given."""
        chs = list(channels) if channels else list(self.channels)
        for ch in chs:
            if ch in self.channels:
                self.channels.remove(ch)
                if ch in self.fake_redis.subscribers and self in self.fake_redis.subscribers[ch]:
                    self.fake_redis.subscribers[ch].remove(self)

    async def get_message(
        self, ignore_subscribe_messages: bool = False, timeout: float | None = 0.0
    ) -> dict[str, Any] | None:
        """Retrieve next queued message or None if timed out."""
        if self.closed:
            return None
        try:
            if timeout is not None and timeout > 0:
                return await asyncio.wait_for(self.queue.get(), timeout=timeout)
            return self.queue.get_nowait()
        except (asyncio.QueueEmpty, TimeoutError):
            return None

    async def aclose(self) -> None:
        """Close pubsub connection and unsubscribe."""
        self.closed = True
        await self.unsubscribe()


class FakeRedis:
    """In-memory Redis client with pub/sub support."""

    def __init__(self) -> None:
        self.subscribers: dict[str, list[FakePubSub]] = {}
        self.published_messages: list[tuple[str, Any]] = []
        self.closed = False

    def pubsub(self) -> FakePubSub:
        """Create a new PubSub subscriber."""
        return FakePubSub(self)

    async def publish(self, channel: str, message: Any) -> int:
        """Publish a message to channel and deliver to subscribers."""
        self.published_messages.append((channel, message))
        if channel not in self.subscribers:
            self.subscribers[channel] = []
        subs = list(self.subscribers[channel])
        for sub in subs:
            await sub.queue.put({"type": "message", "channel": channel, "data": message})
        return len(subs)

    async def ping(self) -> bool:
        """Ping Redis."""
        return True

    async def aclose(self) -> None:
        """Close Redis connection."""
        self.closed = True
