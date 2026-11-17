from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Board(TimestampMixin, Base):
    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")


class BoardColumn(TimestampMixin, Base):
    """A Kanban column ("To Do", "In Progress"...). Named BoardColumn to avoid clashing
    with SQLAlchemy's own `Column`."""

    __tablename__ = "board_columns"

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(50))
    position: Mapped[int] = mapped_column(Integer, default=0)
    # Tasks in a "done" column count as completed in analytics.
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)


class Label(TimestampMixin, Base):
    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(30))
    color: Mapped[str] = mapped_column(String(7), default="#6366f1")  # hex colour
