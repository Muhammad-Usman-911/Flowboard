"""Keeps track of the WebSockets connected to *this* process, grouped by board."""

import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger("app.realtime")


class ConnectionManager:
    def __init__(self) -> None:
        self._boards: dict[int, set[WebSocket]] = defaultdict(set)

    def connect(self, board_id: int, websocket: WebSocket) -> None:
        self._boards[board_id].add(websocket)

    def disconnect(self, board_id: int, websocket: WebSocket) -> None:
        sockets = self._boards.get(board_id)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            del self._boards[board_id]

    def count(self, board_id: int) -> int:
        return len(self._boards.get(board_id, ()))

    async def broadcast(self, board_id: int, message: str) -> None:
        """Send a message to every local socket on a board. Dead sockets are dropped."""
        sockets = list(self._boards.get(board_id, ()))
        if not sockets:
            return
        results = await asyncio.gather(
            *(ws.send_text(message) for ws in sockets), return_exceptions=True
        )
        for ws, result in zip(sockets, results, strict=True):
            if isinstance(result, Exception):
                self.disconnect(board_id, ws)
