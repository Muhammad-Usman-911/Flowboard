from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import Access, CurrentUser, SessionDep, workspace_access
from app.models import Role
from app.schemas.collaboration import ActivityOut, AnalyticsOut
from app.schemas.common import Page, PageParams, page_params
from app.schemas.workspace import (
    MemberInvite,
    MemberOut,
    MemberUpdate,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceUpdate,
    WorkspaceWithRole,
)
from app.services.activity import ActivityService
from app.services.analytics import AnalyticsService
from app.services.workspaces import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
PageDep = Annotated[PageParams, Depends(page_params)]


@router.post("", response_model=WorkspaceWithRole, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    data: WorkspaceCreate, user: CurrentUser, session: SessionDep
) -> WorkspaceWithRole:
    """Create a workspace. You become its Owner."""
    workspace = await WorkspaceService(session).create(data, user)
    return WorkspaceWithRole(
        **WorkspaceOut.model_validate(workspace).model_dump(), my_role=Role.OWNER
    )


@router.get("", response_model=Page[WorkspaceWithRole])
async def list_workspaces(
    user: CurrentUser, session: SessionDep, page: PageDep
) -> Page[WorkspaceWithRole]:
    """Workspaces you are a member of, with your role in each."""
    rows, total = await WorkspaceService(session).list_for_user(user, page.limit, page.offset)
    items = [
        WorkspaceWithRole(**WorkspaceOut.model_validate(ws).model_dump(), my_role=role)
        for ws, role in rows
    ]
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/{workspace_id}", response_model=WorkspaceWithRole)
async def get_workspace(
    workspace_id: int,
    session: SessionDep,
    access: Annotated[Access, Depends(workspace_access(Role.VIEWER))],
) -> WorkspaceWithRole:
    workspace = await WorkspaceService(session).get(workspace_id)
    return WorkspaceWithRole(
        **WorkspaceOut.model_validate(workspace).model_dump(), my_role=access.member.role
    )


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
async def update_workspace(
    workspace_id: int,
    data: WorkspaceUpdate,
    session: SessionDep,
    access: Annotated[Access, Depends(workspace_access(Role.ADMIN))],
) -> WorkspaceOut:
    """Rename or describe the workspace (Admin+)."""
    workspace = await WorkspaceService(session).update(workspace_id, data, access.user)
    return WorkspaceOut.model_validate(workspace)


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(workspace_access(Role.OWNER))],
)
async def delete_workspace(workspace_id: int, session: SessionDep) -> Response:
    """Delete the workspace and everything in it (Owner only)."""
    await WorkspaceService(session).delete(workspace_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- members ---
@router.get(
    "/{workspace_id}/members",
    response_model=Page[MemberOut],
    dependencies=[Depends(workspace_access(Role.VIEWER))],
)
async def list_members(workspace_id: int, session: SessionDep, page: PageDep) -> Page[MemberOut]:
    items, total = await WorkspaceService(session).list_members(
        workspace_id, page.limit, page.offset
    )
    return Page(
        items=[MemberOut.model_validate(m) for m in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "/{workspace_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED
)
async def invite_member(
    workspace_id: int,
    data: MemberInvite,
    session: SessionDep,
    access: Annotated[Access, Depends(workspace_access(Role.ADMIN))],
) -> MemberOut:
    """Add a registered user by email with a role (Admin+; only the Owner can add Admins)."""
    member = await WorkspaceService(session).invite(workspace_id, data, access.member)
    return MemberOut.model_validate(member)


@router.patch("/{workspace_id}/members/{user_id}", response_model=MemberOut)
async def change_member_role(
    workspace_id: int,
    user_id: int,
    data: MemberUpdate,
    session: SessionDep,
    access: Annotated[Access, Depends(workspace_access(Role.ADMIN))],
) -> MemberOut:
    member = await WorkspaceService(session).change_role(
        workspace_id, user_id, data.role, access.member
    )
    return MemberOut.model_validate(member)


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    workspace_id: int,
    user_id: int,
    session: SessionDep,
    access: Annotated[Access, Depends(workspace_access(Role.VIEWER))],
) -> Response:
    """Remove a member (Admin+), or leave the workspace yourself (any role but Owner)."""
    await WorkspaceService(session).remove(workspace_id, user_id, access.member)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- activity & analytics ---
@router.get(
    "/{workspace_id}/activity",
    response_model=Page[ActivityOut],
    dependencies=[Depends(workspace_access(Role.VIEWER))],
)
async def list_activity(
    workspace_id: int,
    session: SessionDep,
    page: PageDep,
    board_id: Annotated[int | None, Query()] = None,
    task_id: Annotated[int | None, Query()] = None,
) -> Page[ActivityOut]:
    """The activity log, newest first. Narrow it with `board_id` or `task_id`."""
    items, total = await ActivityService(session).list_entries(
        workspace_id, board_id, task_id, page.limit, page.offset
    )
    return Page(
        items=[ActivityOut.model_validate(a) for a in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/{workspace_id}/analytics",
    response_model=AnalyticsOut,
    dependencies=[Depends(workspace_access(Role.VIEWER))],
)
async def workspace_analytics(
    workspace_id: int,
    session: SessionDep,
    board_id: Annotated[int | None, Query(description="Only this board")] = None,
    weeks: Annotated[int, Query(ge=1, le=52)] = 8,
) -> AnalyticsOut:
    """Tasks per status, overdue count, completion rate per member, tasks created per week."""
    return await AnalyticsService(session).summary(workspace_id, board_id, weeks)
