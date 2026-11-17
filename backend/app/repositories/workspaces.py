from sqlalchemy import select

from app.models import Role, Workspace, WorkspaceMember
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository):
    async def get(self, workspace_id: int) -> Workspace | None:
        return await self.session.get(Workspace, workspace_id)

    async def add(self, workspace: Workspace) -> Workspace:
        self.session.add(workspace)
        await self.session.flush()
        return workspace

    async def delete(self, workspace: Workspace) -> None:
        await self.session.delete(workspace)
        await self.session.flush()

    async def list_for_user(
        self, user_id: int, limit: int, offset: int
    ) -> tuple[list[tuple[Workspace, Role]], int]:
        stmt = (
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.created_at, Workspace.id)
        )
        total = await self.count(stmt)
        rows = await self.session.execute(stmt.limit(limit).offset(offset))
        return [(ws, role) for ws, role in rows.all()], total

    # --- members ---
    async def get_member(self, workspace_id: int, user_id: int) -> WorkspaceMember | None:
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_members(
        self, workspace_id: int, limit: int, offset: int
    ) -> tuple[list[WorkspaceMember], int]:
        stmt = (
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.created_at, WorkspaceMember.id)
        )
        return await self.paginate(stmt, limit, offset)

    async def member_user_ids(self, workspace_id: int) -> set[int]:
        stmt = select(WorkspaceMember.user_id).where(WorkspaceMember.workspace_id == workspace_id)
        return set((await self.session.execute(stmt)).scalars().all())

    async def add_member(self, member: WorkspaceMember) -> WorkspaceMember:
        self.session.add(member)
        await self.session.flush()
        return member

    async def remove_member(self, member: WorkspaceMember) -> None:
        await self.session.delete(member)
        await self.session.flush()
