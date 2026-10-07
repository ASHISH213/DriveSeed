"""Redis client and connection management."""

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import get_settings

_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    """Get or create singleton async Redis client."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis_client


async def check_redis_connection() -> bool:
    """Send ping to verify Redis connectivity."""
    try:
        client = get_redis_client()
        result = await client.ping()
        return bool(result)
    except Exception:
        return False


async def close_redis_connection() -> None:
    """Close async Redis client connections."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
