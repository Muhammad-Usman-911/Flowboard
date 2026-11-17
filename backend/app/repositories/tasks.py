from datetime import date

from sqlalchemy import Select, func, or_, select

from app.models import BoardColumn, Task, task_labels
from app.repositories.base import BaseRepository
from app.schemas.task import TaskFilters


class TaskRepository(BaseRepository):
    async def get(self, task_id: int) -> Task | None:
        return await self.session.get(Task, task_id)

    async def add(self, task: Task) -> Task:
        self.session.add(task)
        await self.session.flush()
        return task

    async def delete(self, task: Task) -> None:
        await self.session.delete(task)
        await self.session.flush()

    async def refresh(self, task: Task) -> Task:
        """Reload a task (and its relationships) after an update."""
        await self.session.refresh(task, attribute_names=["labels", "assignee", "updated_at"])
        return task

    async def list_in_column(self, column_id: int, *, for_update: bool = False) -> list[Task]:
        """All tasks of a column in display order. `for_update` locks the rows (SELECT ...
        FOR UPDATE) so two people moving tasks at the same moment cannot interleave."""
        stmt = select(Task).where(Task.column_id == column_id).order_by(Task.position, Task.id)
        if for_update:
            # populate_existing: overwrite objects already in the session with the fresh,
            # locked values (another request may have changed them a moment ago).
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_in_column(self, column_id: int) -> int:
        stmt = select(func.count()).where(Task.column_id == column_id)
        return (await self.session.execute(stmt)).scalar_one()

    def _filtered(self, board_id: int, f: TaskFilters) -> Select[tuple[Task]]:
        stmt = select(Task).where(Task.board_id == board_id)
        if f.assignee_id is not None:
            stmt = stmt.where(Task.assignee_id == f.assignee_id)
        if f.unassigned:
            stmt = stmt.where(Task.assignee_id.is_(None))
        if f.priority is not None:
            stmt = stmt.where(Task.priority == f.priority)
        if f.column_id is not None:
            stmt = stmt.where(Task.column_id == f.column_id)
        if f.label_id is not None:
            # EXISTS-style filter through the link table.
            stmt = stmt.where(
                Task.id.in_(
                    select(task_labels.c.task_id).where(task_labels.c.label_id == f.label_id)
                )
            )
        if f.due_before is not None:
            stmt = stmt.where(Task.due_date <= f.due_before)
        if f.due_after is not None:
            stmt = stmt.where(Task.due_date >= f.due_after)
        if f.overdue:
            done_columns = select(BoardColumn.id).where(BoardColumn.is_done.is_(True))
            stmt = stmt.where(Task.due_date < date.today(), Task.column_id.not_in(done_columns))
        if f.q:
            # ILIKE = case-insensitive LIKE. Escape % and _ so users can search for them.
            term = f.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{term}%"
            stmt = stmt.where(
                or_(
                    Task.title.ilike(pattern, escape="\\"),
                    Task.description.ilike(pattern, escape="\\"),
                )
            )
        return stmt

    async def search(
        self, board_id: int, filters: TaskFilters, limit: int, offset: int
    ) -> tuple[list[Task], int]:
        stmt = self._filtered(board_id, filters).order_by(Task.column_id, Task.position, Task.id)
        return await self.paginate(stmt, limit, offset)

    async def list_for_board(self, board_id: int) -> list[Task]:
        """All tasks of a board (used to clean up attachment files on board delete)."""
        stmt = select(Task).where(Task.board_id == board_id)
        return list((await self.session.execute(stmt)).scalars().all())
