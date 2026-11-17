from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Role
from app.schemas.common import ORMModel
from app.schemas.user import UserPublic


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Acme Product Team"])
    description: str = Field(default="", max_length=2000)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class WorkspaceOut(ORMModel):
    id: int
    name: str
    description: str
    owner_id: int
    created_at: datetime


class WorkspaceWithRole(WorkspaceOut):
    """A workspace as seen by the current user, including their role in it."""

    my_role: Role


class MemberInvite(BaseModel):
    email: EmailStr = Field(examples=["member@flowboard.dev"])
    role: Role = Field(default=Role.MEMBER, examples=["member"])


class MemberUpdate(BaseModel):
    role: Role


class MemberOut(ORMModel):
    user: UserPublic
    role: Role
    created_at: datetime
