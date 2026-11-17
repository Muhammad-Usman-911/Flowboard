from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.schemas.user import UserPublic


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000, examples=["Looks good @sara_dev!"])


class CommentOut(ORMModel):
    id: int
    task_id: int
    author: UserPublic | None
    body: str
    created_at: datetime


class AttachmentOut(ORMModel):
    id: int
    task_id: int
    uploader_id: int | None
    filename: str
    content_type: str
    size: int
    created_at: datetime


class NotificationOut(ORMModel):
    id: int
    type: str
    message: str
    task_id: int | None
    board_id: int | None
    is_read: bool
    created_at: datetime


class ActivityOut(ORMModel):
    id: int
    workspace_id: int
    board_id: int | None
    task_id: int | None
    user: UserPublic | None
    action: str
    summary: str
    details: dict[str, Any]
    created_at: datetime


class StatusCount(BaseModel):
    """Tasks per status. A status is a column title (summed across boards)."""

    title: str
    is_done: bool
    count: int


class MemberCompletion(BaseModel):
    user: UserPublic
    assigned: int
    completed: int
    completion_rate: float = Field(description="completed / assigned, 0..1")


class WeeklyCount(BaseModel):
    week_start: date
    count: int


class AnalyticsOut(BaseModel):
    total_tasks: int
    completed_tasks: int
    overdue_tasks: int
    tasks_per_status: list[StatusCount]
    completion_by_member: list[MemberCompletion]
    tasks_created_per_week: list[WeeklyCount]
