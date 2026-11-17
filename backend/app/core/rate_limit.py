"""A tiny fixed-window rate limiter on top of Redis.

INCR a counter key; the first hit also sets an expiry. If the counter goes over the limit
inside the window, the request is rejected. Because the counter lives in Redis, the limit
is shared by every API instance (unlike an in-memory dict).
"""

from redis.asyncio import Redis

from app.core.errors import RateLimitError


async def hit(redis: Redis, key: str, limit: int, window_seconds: int) -> None:
    """Count one attempt for `key`; raise RateLimitError when over `limit`."""
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    if count > limit:
        ttl = await redis.ttl(key)
        raise RateLimitError(f"Too many attempts. Try again in {max(ttl, 1)} seconds.")


async def reset(redis: Redis, key: str) -> None:
    await redis.delete(key)
