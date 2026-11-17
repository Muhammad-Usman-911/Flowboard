"""Workspaces and membership management."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models import Role, User, Workspace, WorkspaceMember
from app.repositories.users import UserRepository
from app.repositories.workspaces import WorkspaceRepository
from app.schemas.workspace import MemberInvite, WorkspaceCreate, WorkspaceUpdate
from app.services.activity import ActivityService


class WorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WorkspaceRepository(session)
        self.users = UserRepository(session)
        self.activity = ActivityService(session)

    async def create(self, data: WorkspaceCreate, owner: User) -> Workspace:
        workspace = await self.repo.add(
            Workspace(name=data.name, description=data.description, owner_id=owner.id)
        )
        await self.repo.add_member(
            WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role=Role.OWNER)
        )
        await self.activity.record(
            workspace_id=workspace.id,
            user_id=owner.id,
            action="workspace.created",
            summary=f"created workspace '{workspace.name}'",
        )
        await self.session.commit()
        await self.session.refresh(workspace)
        return workspace

    async def list_for_user(
        self, user: User, limit: int, offset: int
    ) -> tuple[list[tuple[Workspace, Role]], int]:
        return await self.repo.list_for_user(user.id, limit, offset)

    async def get(self, workspace_id: int) -> Workspace:
        workspace = await self.repo.get(workspace_id)
        if workspace is None:
            raise NotFoundError("Workspace not found")
        return workspace

    async def update(self, workspace_id: int, data: WorkspaceUpdate, actor: User) -> Workspace:
        workspace = await self.get(workspace_id)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in changes.items():
            setattr(workspace, field, value)
        await self.activity.record(
            workspace_id=workspace.id,
            user_id=actor.id,
            action="workspace.updated",
            summary=f"updated workspace '{workspace.name}'",
            details={"fields": sorted(changes)},
        )
        await self.session.commit()
        return workspace

    async def delete(self, workspace_id: int) -> None:
        await self.repo.delete(await self.get(workspace_id))
        await self.session.commit()

    # --- members ---
    async def list_members(
        self, workspace_id: int, limit: int, offset: int
    ) -> tuple[list[WorkspaceMember], int]:
        return await self.repo.list_members(workspace_id, limit, offset)

    async def invite(
        self, workspace_id: int, data: MemberInvite, actor: WorkspaceMember
    ) -> WorkspaceMember:
        if data.role == Role.OWNER:
            raise ForbiddenError("A workspace has exactly one owner", "cannot_add_owner")
        if data.role == Role.ADMIN and actor.role != Role.OWNER:
            raise ForbiddenError("Only the owner can add admins", "insufficient_role")
        user = await self.users.get_by_email(data.email)
        if user is None:
            raise NotFoundError("No user with this email has registered yet", "user_not_found")
        if await self.repo.get_member(workspace_id, user.id):
            raise ConflictError("This user is already a member", "already_member")
        member = await self.repo.add_member(
            WorkspaceMember(workspace_id=workspace_id, user_id=user.id, role=data.role)
        )
        await self.activity.record(
            workspace_id=workspace_id,
            user_id=actor.user_id,
            action="member.added",
            summary=f"added @{user.username} as {data.role.value}",
            details={"user_id": user.id, "role": data.role.value},
        )
        await self.session.commit()
        await self.session.refresh(member)
        return member

    async def _target(self, workspace_id: int, user_id: int) -> WorkspaceMember:
        member = await self.repo.get_member(workspace_id, user_id)
        if member is None:
            raise NotFoundError("Member not found")
        return member

    async def change_role(
        self, workspace_id: int, user_id: int, role: Role, actor: WorkspaceMember
    ) -> WorkspaceMember:
        target = await self._target(workspace_id, user_id)
        if target.role == Role.OWNER or role == Role.OWNER:
            raise ForbiddenError("The owner role cannot be changed here", "owner_protected")
        if Role.ADMIN in (target.role, role) and actor.role != Role.OWNER:
            raise ForbiddenError("Only the owner can promote or demote admins", "insufficient_role")
        old = target.role
        target.role = role
        await self.activity.record(
            workspace_id=workspace_id,
            user_id=actor.user_id,
            action="member.role_changed",
            summary=f"changed @{target.user.username} from {old.value} to {role.value}",
            details={"user_id": user_id, "from": old.value, "to": role.value},
        )
        await self.session.commit()
        return target

    async def remove(self, workspace_id: int, user_id: int, actor: WorkspaceMember) -> None:
        target = await self._target(workspace_id, user_id)
        leaving = target.user_id == actor.user_id
        if target.role == Role.OWNER:
            raise ForbiddenError("The owner cannot be removed", "owner_protected")
        if not leaving:
            if not actor.role.at_least(Role.ADMIN):
                raise ForbiddenError("Only admins can remove members", "insufficient_role")
            if target.role == Role.ADMIN and actor.role != Role.OWNER:
                raise ForbiddenError("Only the owner can remove admins", "insufficient_role")
        username = target.user.username
        await self.repo.remove_member(target)
        await self.activity.record(
            workspace_id=workspace_id,
            user_id=actor.user_id,
            action="member.removed",
            summary=f"@{username} left the workspace" if leaving else f"removed @{username}",
            details={"user_id": user_id},
        )
        await self.session.commit()
