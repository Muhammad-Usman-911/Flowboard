"""Boards, their ordered columns, and labels."""

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models import Board, BoardColumn, Label, User
from app.realtime.events import EventPublisher
from app.repositories.boards import BoardRepository
from app.repositories.collaboration import AttachmentRepository
from app.repositories.tasks import TaskRepository
from app.schemas.board import (
    BoardCreate,
    BoardDetail,
    BoardUpdate,
    ColumnCreate,
    ColumnOut,
    ColumnUpdate,
    LabelCreate,
    LabelOut,
)
from app.services.activity import ActivityService
from app.services.ordering import move_item, renumber
from app.services.storage import LocalStorage


class BoardService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self.session = session
        self.repo = BoardRepository(session)
        self.tasks = TaskRepository(session)
        self.attachments = AttachmentRepository(session)
        self.activity = ActivityService(session)
        self.events = EventPublisher(redis)
        self.storage = LocalStorage()

    # --- boards ---
    async def create(self, workspace_id: int, data: BoardCreate, actor: User) -> Board:
        board = await self.repo.add(
            Board(workspace_id=workspace_id, name=data.name, description=data.description)
        )
        for position, title in enumerate(data.columns):
            await self.repo.add_column(
                BoardColumn(
                    board_id=board.id,
                    title=title[:50],
                    position=position,
                    is_done=position == len(data.columns) - 1 and len(data.columns) > 1,
                )
            )
        await self.activity.record(
            workspace_id=workspace_id,
            user_id=actor.id,
            board_id=board.id,
            action="board.created",
            summary=f"created board '{board.name}'",
        )
        await self.session.commit()
        await self.session.refresh(board)
        return board

    async def list_boards(
        self, workspace_id: int, limit: int, offset: int
    ) -> tuple[list[Board], int]:
        return await self.repo.list_for_workspace(workspace_id, limit, offset)

    async def get(self, board_id: int) -> Board:
        board = await self.repo.get(board_id)
        if board is None:
            raise NotFoundError("Board not found")
        return board

    async def detail(self, board_id: int) -> BoardDetail:
        board = await self.get(board_id)
        columns = await self.repo.list_columns(board_id)
        labels = await self.repo.list_labels(board_id)
        return BoardDetail(
            id=board.id,
            workspace_id=board.workspace_id,
            name=board.name,
            description=board.description,
            created_at=board.created_at,
            columns=[ColumnOut.model_validate(c) for c in columns],
            labels=[LabelOut.model_validate(label) for label in labels],
        )

    async def update(self, board_id: int, data: BoardUpdate, actor: User) -> Board:
        board = await self.get(board_id)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in changes.items():
            setattr(board, field, value)
        await self.activity.record(
            workspace_id=board.workspace_id,
            user_id=actor.id,
            board_id=board.id,
            action="board.updated",
            summary=f"updated board '{board.name}'",
            details={"fields": sorted(changes)},
        )
        await self.session.commit()
        await self.events.publish(board.id, "board.updated", {"id": board.id}, actor.id)
        return board

    async def delete(self, board_id: int, actor: User) -> None:
        board = await self.get(board_id)
        task_ids = [t.id for t in await self.tasks.list_for_board(board_id)]
        files = await self.attachments.stored_names_for_tasks(task_ids)
        await self.repo.delete(board)
        await self.activity.record(
            workspace_id=board.workspace_id,
            user_id=actor.id,
            board_id=board_id,
            action="board.deleted",
            summary=f"deleted board '{board.name}'",
        )
        await self.session.commit()
        for name in files:  # remove files only after the DB change is committed
            self.storage.delete(name)
        await self.events.publish(board_id, "board.deleted", {"id": board_id}, actor.id)

    # --- columns ---
    async def get_column(self, column_id: int) -> BoardColumn:
        column = await self.repo.get_column(column_id)
        if column is None:
            raise NotFoundError("Column not found")
        return column

    async def add_column(self, board_id: int, data: ColumnCreate, actor: User) -> BoardColumn:
        board = await self.get(board_id)
        columns = await self.repo.list_columns(board_id, for_update=True)
        column = BoardColumn(board_id=board_id, title=data.title, is_done=data.is_done, position=0)
        index = len(columns) if data.position is None else data.position
        ordered = move_item(columns, column, index)
        renumber(ordered)
        await self.repo.add_column(column)
        await self.activity.record(
            workspace_id=board.workspace_id,
            user_id=actor.id,
            board_id=board_id,
            action="column.created",
            summary=f"added column '{column.title}'",
        )
        await self.session.commit()
        await self.events.publish(
            board_id, "column.created", ColumnOut.model_validate(column).model_dump(), actor.id
        )
        return column

    async def update_column(self, column_id: int, data: ColumnUpdate, actor: User) -> BoardColumn:
        column = await self.get_column(column_id)
        board = await self.get(column.board_id)
        if data.title is not None:
            column.title = data.title
        if data.is_done is not None:
            column.is_done = data.is_done
        if data.position is not None:
            columns = await self.repo.list_columns(column.board_id, for_update=True)
            renumber(move_item(columns, column, data.position))
        await self.activity.record(
            workspace_id=board.workspace_id,
            user_id=actor.id,
            board_id=board.id,
            action="column.updated",
            summary=f"updated column '{column.title}'",
            details=data.model_dump(exclude_none=True),
        )
        await self.session.commit()
        await self.events.publish(
            board.id, "column.updated", ColumnOut.model_validate(column).model_dump(), actor.id
        )
        return column

    async def delete_column(self, column_id: int, actor: User) -> None:
        column = await self.get_column(column_id)
        board = await self.get(column.board_id)
        if await self.tasks.count_in_column(column_id):
            raise ConflictError("Move or delete the tasks in this column first", "column_not_empty")
        columns = await self.repo.list_columns(board.id, for_update=True)
        if len(columns) <= 1:
            raise ConflictError("A board needs at least one column", "last_column")
        await self.repo.delete_column(column)
        renumber([c for c in columns if c.id != column_id])
        await self.activity.record(
            workspace_id=board.workspace_id,
            user_id=actor.id,
            board_id=board.id,
            action="column.deleted",
            summary=f"deleted column '{column.title}'",
        )
        await self.session.commit()
        await self.events.publish(board.id, "column.deleted", {"id": column_id}, actor.id)

    # --- labels ---
    async def list_labels(self, board_id: int, limit: int, offset: int) -> tuple[list[Label], int]:
        await self.get(board_id)
        return await self.repo.page_labels(board_id, limit, offset)

    async def add_label(self, board_id: int, data: LabelCreate, actor: User) -> Label:
        await self.get(board_id)
        if await self.repo.label_name_exists(board_id, data.name):
            raise ConflictError("A label with this name already exists", "label_exists")
        label = await self.repo.add_label(
            Label(board_id=board_id, name=data.name, color=data.color)
        )
        await self.session.commit()
        await self.events.publish(
            board_id, "label.created", LabelOut.model_validate(label).model_dump(), actor.id
        )
        return label

    async def delete_label(self, label_id: int, actor: User) -> None:
        label = await self.repo.get_label(label_id)
        if label is None:
            raise NotFoundError("Label not found")
        board_id = label.board_id
        await self.repo.delete_label(label)
        await self.session.commit()
        await self.events.publish(board_id, "label.deleted", {"id": label_id}, actor.id)
