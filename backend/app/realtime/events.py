"""Publishing board events to Redis.

Every API instance subscribes to the `board:*` channels (see listener.py), so an event
published by *any* instance reaches browsers connected to *every* instance. This is what
lets you run several API containers behind a load balancer.
"""

import json
import logging
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger("app.realtime")

CHANNEL_PREFIX = "board:"


def board_channel(board_id: int) -> str:
    return f"{CHANNEL_PREFIX}{board_id}"


class EventPublisher:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def publish(
        self, board_id: int, event_type: str, data: dict[str, Any], actor_id: int | None
    ) -> None:
        """Send `{"type", "board_id", "actor_id", "data"}` to everyone watching the board.

        Called *after* the DB commit, so listeners never see changes that were rolled back.
        A Redis outage must not break the HTTP request, so errors are logged, not raised.
        """
        message = json.dumps(
            {"type": event_type, "board_id": board_id, "actor_id": actor_id, "data": data},
            default=str,
        )
        try:
            await self.redis.publish(board_channel(board_id), message)
        except Exception:  # pragma: no cover - only when Redis is down
            logger.exception(
                "Could not publish board event", extra={"fields": {"type": event_type}}
            )
