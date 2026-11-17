"""Application factory: builds the FastAPI app, wires middleware, routers and the
background Redis listener.

Run it with:  uvicorn app.main:app --reload
"""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app.api import ws
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.redis import create_redis
from app.db.session import engine
from app.realtime.listener import listen_for_board_events
from app.realtime.manager import ConnectionManager

logger = logging.getLogger("app")

DESCRIPTION = """
**Flowboard** is a real-time Kanban API: workspaces with roles, boards, ordered columns
and tasks, comments with @mentions, attachments, an activity log, analytics and live
updates over WebSockets.

**Try it:** call `POST /api/v1/auth/login` with a seeded account
(`owner@flowboard.dev` / `Password123`), copy the `access_token`, click **Authorize**
and paste it.

Errors always look like `{"detail": "...", "code": "..."}`.
"""


def create_app(redis: Redis | None = None) -> FastAPI:
    """Build the app. Tests pass a fake Redis; production creates a real client."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Startup: one Redis client and one pub/sub listener per process.
        app.state.redis = redis or create_redis()
        app.state.ws_manager = ConnectionManager()
        listener = asyncio.create_task(
            listen_for_board_events(app.state.redis, app.state.ws_manager)
        )
        logger.info("Flowboard API started", extra={"fields": {"env": settings.environment}})
        yield
        # Shutdown: stop the listener and close connections cleanly.
        listener.cancel()
        with suppress(asyncio.CancelledError):
            await listener
        if redis is None:
            await app.state.redis.aclose()

    setup_logging()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=DESCRIPTION,
        lifespan=lifespan,
        openapi_tags=[
            {"name": "auth", "description": "Register, log in and refresh tokens"},
            {"name": "users", "description": "Your profile"},
            {"name": "workspaces", "description": "Workspaces, members, activity, analytics"},
            {"name": "boards", "description": "Boards, columns and labels"},
            {"name": "tasks", "description": "Tasks, filters, move and reorder"},
            {"name": "comments", "description": "Task comments with @mentions"},
            {"name": "attachments", "description": "File uploads (max 10 MB)"},
            {"name": "notifications", "description": "In-app notifications"},
        ],
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """One structured log line per request, with a request id echoed in a header."""
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["x-request-id"] = request_id
        if request.url.path != "/health":
            logger.info(
                "request",
                extra={
                    "fields": {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration_ms": duration_ms,
                    }
                },
            )
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(ws.router)

    @app.get("/health", tags=["health"])
    async def health(request: Request) -> JSONResponse:
        """Liveness + readiness: checks the database and Redis. 503 if either is down."""
        checks: dict[str, str] = {}
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "error"
        try:
            await request.app.state.redis.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"
        healthy = all(v == "ok" for v in checks.values())
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={"status": "ok" if healthy else "degraded", **checks},
        )

    return app


app = create_app()
