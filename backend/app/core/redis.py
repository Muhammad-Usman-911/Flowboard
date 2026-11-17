"""The shared Redis client.

The client is created in the app lifespan (see app/main.py) and stored on `app.state`.
Routes get it through the `get_redis` dependency, which makes it easy to swap in a fake
Redis in tests.
"""

from fastapi import Request, WebSocket
from redis.asyncio import Redis

from app.core.config import settings


def create_redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_redis_ws(websocket: WebSocket) -> Redis:
    return websocket.app.state.redis
