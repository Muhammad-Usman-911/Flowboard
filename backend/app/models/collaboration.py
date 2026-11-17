"""Comments, attachments, notifications and the activity log."""

from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.user import User


class Comment(TimestampMixin, Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text)

    author: Mapped[User | None] = relationship(lazy="joined")


class Attachment(TimestampMixin, Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    uploader_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255))  # original name, shown to users
    stored_name: Mapped[str] = mapped_column(String(64), unique=True)  # random name on disk
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(BigInteger)


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(30))  # "mention" | "assigned"
    message: Mapped[str] = mapped_column(String(300))
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True
    )
    board_id: Mapped[int | None] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=True
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)


class ActivityLog(TimestampMixin, Base):
    """An append-only record of who did what. Board/task ids are plain integers (no FK)
    so the history survives when the board or task is deleted."""

    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    board_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    task_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50))  # e.g. "task.moved"
    summary: Mapped[str] = mapped_column(String(300))  # e.g. "moved 'Fix login' to Done"
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    user: Mapped[User | None] = relationship(lazy="joined")
