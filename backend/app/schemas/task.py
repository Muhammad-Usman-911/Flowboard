from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import Priority
from app.schemas.board import LabelOut
from app.schemas.common import ORMModel
from app.schemas.user import UserPublic


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["Design the login page"])
    description: str = Field(default="", max_length=10_000)
    column_id: int | None = Field(default=None, description="Defaults to the first column")
    priority: Priority = Priority.MEDIUM
    due_date: date | None = None
    assignee_id: int | None = None
    label_ids: list[int] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    """Partial update: only fields you send are changed (send null to clear a field)."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    priority: Priority | None = None
    due_date: date | None = None
    assignee_id: int | None = None
    label_ids: list[int] | None = None


class TaskMove(BaseModel):
    column_id: int = Field(description="Target column (can be the same column)")
    position: int = Field(ge=0, description="0-based index inside the target column")


class TaskOut(ORMModel):
    id: int
    board_id: int
    column_id: int
    title: str
    description: str
    priority: Priority
    due_date: date | None
    position: int
    assignee: UserPublic | None
    created_by_id: int | None
    labels: list[LabelOut]
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskFilters(BaseModel):
    """Filters for GET /boards/{id}/tasks. All are optional and combined with AND."""

    assignee_id: int | None = None
    unassigned: bool = False
    priority: Priority | None = None
    label_id: int | None = None
    column_id: int | None = None
    due_before: date | None = None
    due_after: date | None = None
    overdue: bool = False
    q: str | None = Field(default=None, max_length=100, description="Text search")
