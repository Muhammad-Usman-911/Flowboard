"""Shared test fixtures.

How the test setup works (see docs/LEARNING_GUIDE.md, "Test fixtures"):
1. Before anything is imported, point the app at a separate *test* database.
2. `pytest_configure` creates that database if needed and runs the Alembic migrations,
   so every run also proves the migrations work.
3. Each test gets an HTTP client wired straight into the app (no real network), and all
   tables are emptied after the test, so tests never see each other's data.
4. Redis is fakeredis (in memory) unless TEST_REDIS_URL points at a real server (CI).
"""

import asyncio
import os
import shutil
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://flowboard:flowboard@localhost:55433/flowboard_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "test"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="flowboard-test-uploads-")
os.environ["LOG_JSON"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["BCRYPT_ROUNDS"] = "4"  # fast hashing in tests only

import asyncpg  # noqa: E402
import fakeredis  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from redis.asyncio import Redis  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import create_app  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "Password123"


async def _ensure_database() -> None:
    """CREATE DATABASE flowboard_test if it does not exist yet."""
    dsn = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    base_dsn, db_name = dsn.rsplit("/", 1)
    conn = await asyncpg.connect(f"{base_dsn}/postgres")
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


def pytest_configure(config: pytest.Config) -> None:
    asyncio.run(_ensure_database())
    alembic_cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    alembic_cfg.cmd_opts = type("Opts", (), {"x": [f"db_url={TEST_DATABASE_URL}"]})()  # type: ignore[assignment]
    command.downgrade(alembic_cfg, "base")  # start from an empty schema...
    command.upgrade(alembic_cfg, "head")  # ...and build it with the real migrations


@pytest.fixture(scope="session")
async def redis() -> AsyncIterator[Redis]:
    url = os.environ.get("TEST_REDIS_URL")
    client: Redis = (
        Redis.from_url(url, decode_responses=True)
        if url
        else fakeredis.FakeAsyncRedis(decode_responses=True)
    )
    yield client
    await client.aclose()


@pytest.fixture(scope="session")
async def app(redis: Redis) -> AsyncIterator[Any]:
    application = create_app(redis=redis)
    # Run the lifespan (startup/shutdown) ourselves: httpx's ASGITransport doesn't.
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture(autouse=True)
async def _clean_state(redis: Redis) -> AsyncIterator[None]:
    yield
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    await redis.flushdb()
    shutil.rmtree(os.environ["UPLOAD_DIR"], ignore_errors=True)


@pytest.fixture
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------- helpers that create data through the public API ----------

Headers = dict[str, str]


@pytest.fixture
def make_user(client: AsyncClient) -> Callable[..., Awaitable[Headers]]:
    """`headers = await make_user("sara")` registers + logs in, returns auth headers."""

    async def _make(username: str, password: str = PASSWORD) -> Headers:
        email = f"{username}@example.com"
        r = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": username,
                "full_name": username.title(),
                "password": password,
            },
        )
        assert r.status_code == 201, r.text
        r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _make


async def user_id(client: AsyncClient, headers: Headers) -> int:
    r = await client.get("/api/v1/users/me", headers=headers)
    return r.json()["id"]


@pytest.fixture
async def owner(make_user: Callable[..., Awaitable[Headers]]) -> Headers:
    return await make_user("owner")


@pytest.fixture
async def workspace(client: AsyncClient, owner: Headers) -> dict[str, Any]:
    r = await client.post("/api/v1/workspaces", json={"name": "Team"}, headers=owner)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
async def board(client: AsyncClient, owner: Headers, workspace: dict[str, Any]) -> dict[str, Any]:
    """A board with columns To Do / In Progress / Done (detail incl. columns)."""
    r = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/boards", json={"name": "Sprint"}, headers=owner
    )
    assert r.status_code == 201, r.text
    r = await client.get(f"/api/v1/boards/{r.json()['id']}", headers=owner)
    return r.json()


@pytest.fixture
def add_member(
    client: AsyncClient, owner: Headers, workspace: dict[str, Any], make_user: Any
) -> Callable[..., Awaitable[Headers]]:
    """`headers = await add_member("vic", "viewer")` creates a user in the workspace."""

    async def _add(username: str, role: str) -> Headers:
        headers = await make_user(username)
        r = await client.post(
            f"/api/v1/workspaces/{workspace['id']}/members",
            json={"email": f"{username}@example.com", "role": role},
            headers=owner,
        )
        assert r.status_code == 201, r.text
        return headers

    return _add


@pytest.fixture
def make_task(
    client: AsyncClient, owner: Headers, board: dict[str, Any]
) -> Callable[..., Awaitable[dict[str, Any]]]:
    async def _make(
        title: str, column: int = 0, headers: Headers | None = None, **fields: Any
    ) -> dict[str, Any]:
        body = {"title": title, "column_id": board["columns"][column]["id"], **fields}
        r = await client.post(
            f"/api/v1/boards/{board['id']}/tasks", json=body, headers=headers or owner
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _make
