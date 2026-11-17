"""WebSocket + Redis pub/sub.

httpx-ws lets us open WebSockets against the ASGI app in-process. The broadcast test is
the whole real-time path: HTTP move -> service commits -> Redis PUBLISH -> listener task
-> ConnectionManager -> every socket on that board.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from httpx import AsyncClient
from httpx_ws import WebSocketDisconnect, aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from app.realtime.events import EventPublisher


@asynccontextmanager
async def ws_client_for(app: Any) -> AsyncIterator[AsyncClient]:
    """A client whose transport speaks WebSocket to the in-process app.

    Not a fixture on purpose: the transport runs the app in an anyio task group, which
    must be opened and closed in the same task (pytest fixtures tear down elsewhere)."""
    async with AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test") as c:
        yield c


def token(headers: dict[str, str]) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


async def next_event(ws: Any, event_type: str, wait_seconds: float = 3.0) -> dict[str, Any]:
    """Read messages until one of `event_type` arrives (skipping others)."""
    async with asyncio.timeout(wait_seconds):
        while True:
            message = json.loads(await ws.receive_text())
            if message["type"] == event_type:
                return message


async def test_rejects_missing_or_bad_token(app, board) -> None:
    async with ws_client_for(app) as ws_client:
        for query in ("", "?token=garbage"):
            async with aconnect_ws(f"/ws/boards/{board['id']}{query}", ws_client) as ws:
                with pytest.raises(WebSocketDisconnect) as exc:
                    await ws.receive_text()
                assert exc.value.code == 4401


async def test_rejects_non_members(app, board, make_user) -> None:
    stranger = await make_user("stranger")
    url = f"/ws/boards/{board['id']}?token={token(stranger)}"
    async with ws_client_for(app) as ws_client, aconnect_ws(url, ws_client) as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            await ws.receive_text()
        assert exc.value.code == 4404


async def test_ping_pong(app, board, owner) -> None:
    url = f"/ws/boards/{board['id']}?token={token(owner)}"
    async with ws_client_for(app) as ws_client, aconnect_ws(url, ws_client) as ws:
        assert json.loads(await ws.receive_text()) == {"type": "connected", "board_id": board["id"]}
        await ws.send_text("ping")
        assert json.loads(await ws.receive_text()) == {"type": "pong"}


async def test_task_events_reach_every_connected_member(
    client: AsyncClient, board, owner, add_member, make_task, app
) -> None:
    viewer = await add_member("vic", "viewer")
    task = await make_task("Live task")
    done = board["columns"][2]["id"]
    url = f"/ws/boards/{board['id']}"

    async with (
        ws_client_for(app) as ws_client,
        aconnect_ws(f"{url}?token={token(owner)}", ws_client) as ws_owner,
        aconnect_ws(f"{url}?token={token(viewer)}", ws_client) as ws_viewer,
    ):
        await next_event(ws_owner, "connected")
        await next_event(ws_viewer, "connected")
        assert app.state.ws_manager.count(board["id"]) == 2

        r = await client.post(
            f"/api/v1/tasks/{task['id']}/move",
            json={"column_id": done, "position": 0},
            headers=owner,
        )
        assert r.status_code == 200

        for ws in (ws_owner, ws_viewer):
            event = await next_event(ws, "task.moved")
            assert event["board_id"] == board["id"]
            assert event["data"]["id"] == task["id"]
            assert event["data"]["column_id"] == done
            assert event["data"]["from_column_id"] == board["columns"][0]["id"]

        await client.post(
            f"/api/v1/tasks/{task['id']}/comments", json={"body": "nice"}, headers=owner
        )
        event = await next_event(ws_viewer, "comment.created")
        assert event["data"]["body"] == "nice"

        await client.delete(f"/api/v1/tasks/{task['id']}", headers=owner)
        event = await next_event(ws_viewer, "task.deleted")
        assert event["data"] == {"id": task["id"], "column_id": done}

    # Closed sockets are forgotten.
    for _ in range(50):
        if app.state.ws_manager.count(board["id"]) == 0:
            break
        await asyncio.sleep(0.02)
    assert app.state.ws_manager.count(board["id"]) == 0


async def test_events_from_another_instance_are_delivered(app, board, owner, redis) -> None:
    """Simulate a second API server: publishing straight to Redis must reach our socket."""
    url = f"/ws/boards/{board['id']}?token={token(owner)}"
    async with ws_client_for(app) as ws_client, aconnect_ws(url, ws_client) as ws:
        await next_event(ws, "connected")
        await EventPublisher(redis).publish(board["id"], "task.updated", {"id": 1}, actor_id=None)
        event = await next_event(ws, "task.updated")
        assert event["data"] == {"id": 1}


async def test_events_for_other_boards_are_not_delivered(app, board, owner, redis) -> None:
    url = f"/ws/boards/{board['id']}?token={token(owner)}"
    async with ws_client_for(app) as ws_client, aconnect_ws(url, ws_client) as ws:
        await next_event(ws, "connected")
        await EventPublisher(redis).publish(board["id"] + 1, "task.updated", {"id": 1}, None)
        with pytest.raises(TimeoutError):
            await next_event(ws, "task.updated", wait_seconds=0.5)
