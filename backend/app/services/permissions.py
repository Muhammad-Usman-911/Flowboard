"""Role checks. A user's role is stored per workspace (WorkspaceMember.role).

Rules used across the API:
- Viewer: read everything in the workspace.
- Member: also create/edit tasks, comments and attachments.
- Admin: also manage boards, columns, labels and members (but not the owner).
- Owner: also delete the workspace and promote/demote admins.

Non-members get 404 (not 403) so they cannot even learn that a workspace exists.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.models import Role, WorkspaceMember
from app.repositories.lookups import LookupRepository
from app.repositories.workspaces import WorkspaceRepository


class PermissionService:
    def __init__(self, session: AsyncSession) -> None:
        self.workspaces = WorkspaceRepository(session)
        self.lookups = LookupRepository(session)

    async def require_role(
        self, workspace_id: int, user_id: int, min_role: Role
    ) -> WorkspaceMember:
        member = await self.workspaces.get_member(workspace_id, user_id)
        if member is None:
            raise NotFoundError("Workspace not found")
        if not member.role.at_least(min_role):
            raise ForbiddenError(
                f"This action needs the '{min_role.value}' role or higher "
                f"(you are '{member.role.value}')",
                "insufficient_role",
            )
        return member

    async def workspace_for(self, kind: str, resource_id: int) -> int:
        """Return the workspace id of a board/column/label/task/comment/attachment."""
        resolver = {
            "board": self.lookups.workspace_of_board,
            "column": self.lookups.workspace_of_column,
            "label": self.lookups.workspace_of_label,
            "task": self.lookups.workspace_of_task,
            "comment": self.lookups.workspace_of_comment,
            "attachment": self.lookups.workspace_of_attachment,
        }[kind]
        workspace_id = await resolver(resource_id)
        if workspace_id is None:
            raise NotFoundError(f"{kind.capitalize()} not found")
        return workspace_id
