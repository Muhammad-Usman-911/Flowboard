from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import Role
from app.models.user import User


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))


class WorkspaceMember(TimestampMixin, Base):
    """Join table between users and workspaces, carrying the user's role."""

    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_member_workspace_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # native_enum=False stores the value as VARCHAR + CHECK constraint, which is far easier
    # to change later than a Postgres ENUM type.
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, length=16, values_callable=lambda e: [m.value for m in e])
    )

    # lazy="joined": loading a member always loads the user in the same query.
    user: Mapped[User] = relationship(lazy="joined")
