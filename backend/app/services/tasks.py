"""Tasks: create, filter, update, move/reorder, delete.

Every write follows the same recipe:
  1. load + validate (raise AppError subclasses on bad input)
  2. change ORM objects and record an activity entry (same transaction)
  3. commit
  4. publish a real-time event to Redis (only after the commit succeeded)
"""

from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.models import Board, BoardColumn, Task, User
from app.realtime.events import EventPublisher
from app.repositories.boards import BoardRepository
from app.repositories.collaboration import AttachmentRepository
from app.repositories.tasks import TaskRepository
from app.repositories.workspaces import WorkspaceRepository
from app.schemas.task import TaskCreate, TaskFilters, TaskMove, TaskOut, TaskUpdate
from app.services.activity import ActivityService
from app.services.notifications import NotificationService
from app.services.ordering import move_item, renumber
from app.services.storage import LocalStorage


class InvalidReferenceError(AppError):
    status_code = 422
    code = "invalid_reference"


def task_payload(task: Task) -> dict[str, Any]:
    """The JSON sent over WebSockets: exactly the same shape as the REST response."""
    return TaskOut.model_validate(task).model_dump(mode="json")


class TaskService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self.session = session
        self.repo = TaskRepository(session)
        self.boards = BoardRepository(session)
        self.workspaces = WorkspaceRepository(session)
        self.attachments = AttachmentRepository(session)
        self.activity = ActivityService(session)
        self.notifications = NotificationService(session)
        self.events = EventPublisher(redis)
        self.storage = LocalStorage()

    # --- helpers ---
    async def get(self, task_id: int) -> Task:
        task = await self.repo.get(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        return task

    async def _board(self, board_id: int) -> Board:
        board = await self.boards.get(board_id)
        if board is None:
            raise NotFoundError("Board not found")
        return board

    async def _column_on_board(self, column_id: int, board_id: int) -> BoardColumn:
        column = await self.boards.get_column(column_id)
        if column is None or column.board_id != board_id:
            raise InvalidReferenceError("Column does not belong to this board")
        return column

    async def _check_assignee(self, assignee_id: int, workspace_id: int) -> None:
        if await self.workspaces.get_member(workspace_id, assignee_id) is None:
            raise InvalidReferenceError("Assignee must be a member of this workspace")

    async def _labels(self, board_id: int, label_ids: list[int]):  # type: ignore[no-untyped-def]
        labels = await self.boards.get_labels(board_id, label_ids)
        if len(labels) != len(set(label_ids)):
            raise InvalidReferenceError("Unknown label for this board")
        return labels

    async def _reload(self, task: Task) -> Task:
        # Re-read the row so server-side values (updated_at) and relationships are fresh.
        await self.session.refresh(task)
        return task

    # --- queries ---
    async def search(
        self, board_id: int, filters: TaskFilters, limit: int, offset: int
    ) -> tuple[list[Task], int]:
        await self._board(board_id)
        return await self.repo.search(board_id, filters, limit, offset)

    # --- commands ---
    async def create(self, board_id: int, data: TaskCreate, actor: User) -> Task:
        board = await self._board(board_id)
        if data.column_id is not None:
            column = await self._column_on_board(data.column_id, board_id)
        else:
            columns = await self.boards.list_columns(board_id)
            if not columns:
                raise InvalidReferenceError("This board has no columns")
            column = columns[0]
        if data.assignee_id is not None:
            await self._check_assignee(data.assignee_id, board.workspace_id)

        task = Task(
            board_id=board_id,
            column_id=column.id,
            title=data.title,
            description=data.description,
            priority=data.priority,
            due_date=data.due_date,
            assignee_id=data.assignee_id,
            created_by_id=actor.id,
            position=await self.repo.count_in_column(column.id),  # append at the bottom
            completed_at=datetime.now(UTC) if column.is_done else None,
        )
        task.labels = await self._labels(board_id, data.label_ids)
        await self.repo.add(task)
        if data.assignee_id is not None:
            await self.notifications.notify_assigned(
                assignee_id=data.assignee_id, actor=actor, task=task
            )
        await self.activity.record(
            workspace_id=board.workspace_id,
            user_id=actor.id,
            board_id=board_id,
            task_id=task.id,
            action="task.created",
            summary=f"created '{task.title}' in {column.title}",
        )
        await self.session.commit()
        await self._reload(task)
        await self.events.publish(board_id, "task.created", task_payload(task), actor.id)
        return task

    async def update(self, task_id: int, data: TaskUpdate, actor: User) -> Task:
        task = await self.get(task_id)
        board = await self._board(task.board_id)
        changes = data.model_dump(exclude_unset=True)  # only fields the client sent
        if changes.get("title") is None:
            changes.pop("title", None)  # title can't be cleared
        if "label_ids" in changes:
            task.labels = await self._labels(task.board_id, changes.pop("label_ids") or [])
            changed = ["labels"]
        else:
            changed = []
        new_assignee = changes.get("assignee_id")
        if "assignee_id" in changes and new_assignee is not None:
            await self._check_assignee(new_assignee, board.workspace_id)
        assignee_changed = "assignee_id" in changes and new_assignee != task.assignee_id

        for field, value in changes.items():
            if field == "description" and value is None:
                value = ""
            if getattr(task, field) != value:
                setattr(task, field, value)
                changed.append(field)

        if assignee_changed and new_assignee is not None:
            await self.notifications.notify_assigned(
                assignee_id=new_assignee, actor=actor, task=task
            )
        await self.activity.record(
            workspace_id=board.workspace_id,
            user_id=actor.id,
            board_id=task.board_id,
            task_id=task.id,
            action="task.updated",
            summary=f"updated {', '.join(changed) or 'nothing'} on '{task.title}'",
            details={"fields": changed},
        )
        await self.session.commit()
        await self._reload(task)
        await self.events.publish(task.board_id, "task.updated", task_payload(task), actor.id)
        return task

    async def move(self, task_id: int, data: TaskMove, actor: User) -> Task:
        """Move a task to `data.column_id` at index `data.position`, in one transaction.

        We lock the rows of every affected column with SELECT ... FOR UPDATE (always in
        ascending column id order, which prevents deadlocks between two concurrent moves),
        then rewrite positions so both columns are 0..n-1 again.
        """
        task = await self.get(task_id)
        board = await self._board(task.board_id)
        target = await self._column_on_board(data.column_id, task.board_id)
        source_id = task.column_id
        source = await self.boards.get_column(source_id)
        assert source is not None

        locked: dict[int, list[Task]] = {}
        for column_id in sorted({source_id, target.id}):
            locked[column_id] = await self.repo.list_in_column(column_id, for_update=True)

        if source_id == target.id:
            renumber(move_item(locked[source_id], task, data.position))
        else:
            renumber([t for t in locked[source_id] if t is not task])
            task.column_id = target.id
            renumber(move_item(locked[target.id], task, data.position))
            # Entering a "done" column completes the task; leaving it re-opens it.
            if target.is_done and not source.is_done:
                task.completed_at = datetime.now(UTC)
            elif source.is_done and not target.is_done:
                task.completed_at = None

        await self.activity.record(
            workspace_id=board.workspace_id,
            user_id=actor.id,
            board_id=task.board_id,
            task_id=task.id,
            action="task.moved",
            summary=(
                f"moved '{task.title}' from {source.title} to {target.title}"
                if source_id != target.id
                else f"reordered '{task.title}' in {target.title}"
            ),
            details={
                "from_column_id": source_id,
                "to_column_id": target.id,
                "position": task.position,
            },
        )
        await self.session.commit()
        await self._reload(task)
        payload = task_payload(task) | {"from_column_id": source_id}
        await self.events.publish(task.board_id, "task.moved", payload, actor.id)
        return task

    async def delete(self, task_id: int, actor: User) -> None:
        task = await self.get(task_id)
        board = await self._board(task.board_id)
        files = await self.attachments.stored_names_for_tasks([task.id])
        column_id, title = task.column_id, task.title
        await self.repo.delete(task)
        renumber(await self.repo.list_in_column(column_id, for_update=True))
        await self.activity.record(
            workspace_id=board.workspace_id,
            user_id=actor.id,
            board_id=board.id,
            task_id=task_id,
            action="task.deleted",
            summary=f"deleted '{title}'",
        )
        await self.session.commit()
        for name in files:
            self.storage.delete(name)
        await self.events.publish(
            board.id, "task.deleted", {"id": task_id, "column_id": column_id}, actor.id
        )
