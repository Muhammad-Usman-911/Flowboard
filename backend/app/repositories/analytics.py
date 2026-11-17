"""Aggregate queries for the analytics dashboard.

These use GROUP BY in the database instead of loading every task into Python: the
database is much faster at counting, and only a handful of rows travel back.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, case, cast, func, select

from app.models import Board, BoardColumn, Task, User
from app.repositories.base import BaseRepository


class AnalyticsRepository(BaseRepository):
    def _scope(self, stmt: Any, workspace_id: int, board_id: int | None) -> Any:
        stmt = stmt.where(Board.workspace_id == workspace_id)
        if board_id is not None:
            stmt = stmt.where(Board.id == board_id)
        return stmt

    async def tasks_per_status(
        self, workspace_id: int, board_id: int | None
    ) -> list[tuple[str, bool, int]]:
        stmt = (
            select(BoardColumn.title, BoardColumn.is_done, func.count(Task.id))
            .join(Board, Board.id == BoardColumn.board_id)
            .outerjoin(Task, Task.column_id == BoardColumn.id)  # keep empty columns
            .group_by(BoardColumn.title, BoardColumn.is_done)
            .order_by(
                BoardColumn.is_done, func.min(BoardColumn.position), BoardColumn.title
            )  # done last
        )
        rows = await self.session.execute(self._scope(stmt, workspace_id, board_id))
        return [(title, is_done, count) for title, is_done, count in rows.all()]

    async def overdue_count(self, workspace_id: int, board_id: int | None, today: date) -> int:
        stmt = (
            select(func.count(Task.id))
            .join(BoardColumn, BoardColumn.id == Task.column_id)
            .join(Board, Board.id == Task.board_id)
            .where(Task.due_date < today, BoardColumn.is_done.is_(False))
        )
        return (await self.session.execute(self._scope(stmt, workspace_id, board_id))).scalar_one()

    async def completion_by_member(
        self, workspace_id: int, board_id: int | None
    ) -> list[tuple[User, int, int]]:
        done = func.count(case((BoardColumn.is_done.is_(True), Task.id)))
        stmt = (
            select(User, func.count(Task.id), done)
            .join(Task, Task.assignee_id == User.id)
            .join(BoardColumn, BoardColumn.id == Task.column_id)
            .join(Board, Board.id == Task.board_id)
            .group_by(User.id)
            .order_by(User.username)
        )
        rows = await self.session.execute(self._scope(stmt, workspace_id, board_id))
        return [(user, assigned, completed) for user, assigned, completed in rows.all()]

    async def created_per_week(
        self, workspace_id: int, board_id: int | None, since: datetime
    ) -> dict[date, int]:
        week = cast(func.date_trunc("week", Task.created_at), Date)
        stmt = (
            select(week, func.count(Task.id))
            .join(Board, Board.id == Task.board_id)
            .where(Task.created_at >= since)
            .group_by(week)
        )
        rows = await self.session.execute(self._scope(stmt, workspace_id, board_id))
        return {week_start: count for week_start, count in rows.all()}
