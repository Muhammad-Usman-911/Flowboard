from sqlalchemy import func, select

from app.models import Board, BoardColumn, Label
from app.repositories.base import BaseRepository


class BoardRepository(BaseRepository):
    async def get(self, board_id: int) -> Board | None:
        return await self.session.get(Board, board_id)

    async def add(self, board: Board) -> Board:
        self.session.add(board)
        await self.session.flush()
        return board

    async def delete(self, board: Board) -> None:
        await self.session.delete(board)
        await self.session.flush()

    async def list_for_workspace(
        self, workspace_id: int, limit: int, offset: int
    ) -> tuple[list[Board], int]:
        stmt = (
            select(Board)
            .where(Board.workspace_id == workspace_id)
            .order_by(Board.created_at, Board.id)
        )
        return await self.paginate(stmt, limit, offset)

    # --- columns ---
    async def get_column(self, column_id: int) -> BoardColumn | None:
        return await self.session.get(BoardColumn, column_id)

    async def list_columns(self, board_id: int, *, for_update: bool = False) -> list[BoardColumn]:
        stmt = (
            select(BoardColumn)
            .where(BoardColumn.board_id == board_id)
            .order_by(BoardColumn.position, BoardColumn.id)
        )
        if for_update:
            # populate_existing: overwrite objects already in the session with the fresh,
            # locked values (another request may have changed them a moment ago).
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return list((await self.session.execute(stmt)).scalars().all())

    async def add_column(self, column: BoardColumn) -> BoardColumn:
        self.session.add(column)
        await self.session.flush()
        return column

    async def delete_column(self, column: BoardColumn) -> None:
        await self.session.delete(column)
        await self.session.flush()

    # --- labels ---
    async def get_label(self, label_id: int) -> Label | None:
        return await self.session.get(Label, label_id)

    async def list_labels(self, board_id: int) -> list[Label]:
        stmt = select(Label).where(Label.board_id == board_id).order_by(Label.name)
        return list((await self.session.execute(stmt)).scalars().all())

    async def page_labels(self, board_id: int, limit: int, offset: int) -> tuple[list[Label], int]:
        stmt = select(Label).where(Label.board_id == board_id).order_by(Label.name, Label.id)
        return await self.paginate(stmt, limit, offset)

    async def get_labels(self, board_id: int, label_ids: list[int]) -> list[Label]:
        if not label_ids:
            return []
        stmt = select(Label).where(Label.board_id == board_id, Label.id.in_(label_ids))
        return list((await self.session.execute(stmt)).scalars().all())

    async def label_name_exists(self, board_id: int, name: str) -> bool:
        stmt = select(func.count()).where(
            Label.board_id == board_id, func.lower(Label.name) == name.lower()
        )
        return (await self.session.execute(stmt)).scalar_one() > 0

    async def add_label(self, label: Label) -> Label:
        self.session.add(label)
        await self.session.flush()
        return label

    async def delete_label(self, label: Label) -> None:
        await self.session.delete(label)
        await self.session.flush()
