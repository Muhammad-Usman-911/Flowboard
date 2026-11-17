"""Find which workspace a resource belongs to. Permission checks need this: a role is
held per workspace, so "may I edit task 42?" starts with "which workspace is task 42 in?"."""

from sqlalchemy import select

from app.models import Attachment, Board, BoardColumn, Comment, Label, Task
from app.repositories.base import BaseRepository


class LookupRepository(BaseRepository):
    async def _one(self, stmt) -> int | None:  # type: ignore[no-untyped-def]
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def workspace_of_board(self, board_id: int) -> int | None:
        return await self._one(select(Board.workspace_id).where(Board.id == board_id))

    async def workspace_of_column(self, column_id: int) -> int | None:
        stmt = (
            select(Board.workspace_id)
            .join(BoardColumn, BoardColumn.board_id == Board.id)
            .where(BoardColumn.id == column_id)
        )
        return await self._one(stmt)

    async def workspace_of_label(self, label_id: int) -> int | None:
        stmt = (
            select(Board.workspace_id)
            .join(Label, Label.board_id == Board.id)
            .where(Label.id == label_id)
        )
        return await self._one(stmt)

    async def workspace_of_task(self, task_id: int) -> int | None:
        stmt = (
            select(Board.workspace_id)
            .join(Task, Task.board_id == Board.id)
            .where(Task.id == task_id)
        )
        return await self._one(stmt)

    async def workspace_of_comment(self, comment_id: int) -> int | None:
        stmt = (
            select(Board.workspace_id)
            .join(Task, Task.board_id == Board.id)
            .join(Comment, Comment.task_id == Task.id)
            .where(Comment.id == comment_id)
        )
        return await self._one(stmt)

    async def workspace_of_attachment(self, attachment_id: int) -> int | None:
        stmt = (
            select(Board.workspace_id)
            .join(Task, Task.board_id == Board.id)
            .join(Attachment, Attachment.task_id == Task.id)
            .where(Attachment.id == attachment_id)
        )
        return await self._one(stmt)
