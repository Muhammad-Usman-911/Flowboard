from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.board import Label
from app.models.enums import Priority
from app.models.user import User

# Many-to-many link table between tasks and labels (no extra data, so a plain Table).
task_labels = Table(
    "task_labels",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("label_id", ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True),
)


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    # Tasks are always read "per column, in order", so index exactly that.
    __table_args__ = (Index("ix_tasks_column_position", "column_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # board_id is also reachable through column_id, but storing it makes filters and
    # permission checks a single lookup (a deliberate, small denormalisation).
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    column_id: Mapped[int] = mapped_column(ForeignKey("board_columns.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[Priority] = mapped_column(
        Enum(
            Priority, native_enum=False, length=16, values_callable=lambda e: [m.value for m in e]
        ),
        default=Priority.MEDIUM,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # selectin: labels/assignee are loaded with one extra query for *all* tasks in a list,
    # which avoids the "N+1 queries" problem.
    labels: Mapped[list[Label]] = relationship(secondary=task_labels, lazy="selectin")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="selectin")
