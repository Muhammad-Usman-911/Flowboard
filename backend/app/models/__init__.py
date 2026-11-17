"""Import every model here so `Base.metadata` knows all tables (Alembic relies on it)."""

from app.models.board import Board, BoardColumn, Label
from app.models.collaboration import ActivityLog, Attachment, Comment, Notification
from app.models.enums import Priority, Role
from app.models.task import Task, task_labels
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember

__all__ = [
    "ActivityLog",
    "Attachment",
    "Board",
    "BoardColumn",
    "Comment",
    "Label",
    "Notification",
    "Priority",
    "Role",
    "Task",
    "User",
    "Workspace",
    "WorkspaceMember",
    "task_labels",
]
