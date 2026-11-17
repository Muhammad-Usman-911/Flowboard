"""Background task: Redis pub/sub -> local WebSockets.

Started once per process in the app lifespan. It subscribes to the pattern `board:*`
and forwards each message to the sockets this process holds for that board.
"""

import asyncio
import contextlib
import logging

from redis.asyncio import Redis

from app.realtime.events import CHANNEL_PREFIX
from app.realtime.manager import ConnectionManager

logger = logging.getLogger("app.realtime")


async def listen_for_board_events(redis: Redis, manager: ConnectionManager) -> None:
    backoff = 1.0
    while True:
        pubsub = redis.pubsub()
        try:
            await pubsub.psubscribe(f"{CHANNEL_PREFIX}*")
            logger.info("Subscribed to board events")
            backoff = 1.0
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    continue
                channel = message["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode()
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                board_id = int(channel.removeprefix(CHANNEL_PREFIX))
                await manager.broadcast(board_id, data)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - reconnect loop for Redis outages
            logger.exception("Board event listener failed; retrying in %.0fs", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
        finally:
            with contextlib.suppress(Exception):
                await pubsub.aclose()
