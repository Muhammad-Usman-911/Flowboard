"""Repositories hold *all* SQL. Services call them; routers never do.

Each repository wraps one AsyncSession. Repositories only `flush()` (send SQL so ids are
assigned); the *service* decides when to `commit()`, so several repository calls can
share one transaction.
"""

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count(self, stmt: Select[Any]) -> int:
        """Count the rows `stmt` would return (ignoring any ORDER BY / LIMIT)."""
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        return (await self.session.execute(count_stmt)).scalar_one()

    async def paginate(self, stmt: Select[Any], limit: int, offset: int) -> tuple[list[Any], int]:
        """Run `stmt` for one page (first selected entity only) plus the total count."""
        total = await self.count(stmt)
        rows = (await self.session.execute(stmt.limit(limit).offset(offset))).unique()
        return list(rows.scalars().all()), total
