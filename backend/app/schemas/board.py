import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class ColumnCreate(BaseModel):
    title: str = Field(min_length=1, max_length=50, examples=["In Review"])
    is_done: bool = False
    position: int | None = Field(default=None, ge=0, description="Defaults to the end")


class ColumnUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=50)
    is_done: bool | None = None
    position: int | None = Field(default=None, ge=0, description="Move the column")


class ColumnOut(ORMModel):
    id: int
    board_id: int
    title: str
    position: int
    is_done: bool


class LabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=30, examples=["bug"])
    color: str = Field(default="#6366f1", examples=["#ef4444"])

    @field_validator("color")
    @classmethod
    def valid_color(cls, value: str) -> str:
        if not HEX_COLOR.match(value):
            raise ValueError("Color must be a hex value like #ef4444")
        return value.lower()


class LabelOut(ORMModel):
    id: int
    board_id: int
    name: str
    color: str


class BoardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Website relaunch"])
    description: str = Field(default="", max_length=2000)
    # New boards get these columns; the last one is marked "done".
    columns: list[str] = Field(
        default_factory=lambda: ["To Do", "In Progress", "Done"], max_length=20
    )


class BoardUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class BoardOut(ORMModel):
    id: int
    workspace_id: int
    name: str
    description: str
    created_at: datetime


class BoardDetail(BoardOut):
    """A board with its ordered columns and labels (tasks are fetched separately)."""

    columns: list[ColumnOut]
    labels: list[LabelOut]
