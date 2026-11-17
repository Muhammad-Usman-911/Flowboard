"""WebSocket endpoint: /ws/boards/{board_id}?token=<access token>

Browsers cannot set an Authorization header on a WebSocket, so the access token travels
in the query string. After the handshake the server only *sends* events; the client may
send "ping" to keep the connection alive and gets {"type": "pong"} back.

Close codes (4000-4999 are free for applications to use):
  4401 = missing/invalid/expired token, 4404 = board not found or you are not a member.
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.errors import AppError
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models import Role
from app.realtime.manager import ConnectionManager
from app.services.permissions import PermissionService

logger = logging.getLogger("app.ws")
router = APIRouter()


async def _authorize(board_id: int, token: str | None) -> int:
    """Return the user id, or raise AppError. Uses its own short-lived DB session so we
    don't hold a database connection open for the whole life of the socket."""
    if not token:
        raise AppError("Missing token", "not_authenticated")
    user_id = decode_token(token, "access")
    async with SessionLocal() as session:
        permissions = PermissionService(session)
        workspace_id = await permissions.workspace_for("board", board_id)
        await permissions.require_role(workspace_id, user_id, Role.VIEWER)
    return user_id


@router.websocket("/ws/boards/{board_id}")
async def board_socket(websocket: WebSocket, board_id: int, token: str | None = None) -> None:
    await websocket.accept()
    try:
        user_id = await _authorize(board_id, token)
    except AppError as exc:
        code = 4404 if exc.status_code in (403, 404) else 4401
        await websocket.close(code=code, reason=exc.detail[:120])
        return

    manager: ConnectionManager = websocket.app.state.ws_manager
    manager.connect(board_id, websocket)
    logger.info("WebSocket connected", extra={"fields": {"board_id": board_id, "user_id": user_id}})
    try:
        await websocket.send_text(json.dumps({"type": "connected", "board_id": board_id}))
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text('{"type": "pong"}')
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(board_id, websocket)
        logger.info(
            "WebSocket closed", extra={"fields": {"board_id": board_id, "user_id": user_id}}
        )
