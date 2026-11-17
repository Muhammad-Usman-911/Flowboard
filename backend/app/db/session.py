"""Async database engine and session factory.

- The *engine* owns a pool of connections to Postgres (one per process).
- A *session* is a unit of work: you load/add objects, then `commit()` (or roll back).
- `get_session` is a FastAPI dependency: one session per request, always closed after.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)

# expire_on_commit=False: objects stay usable after commit (we serialize them afterwards).
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
