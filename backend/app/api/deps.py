"""FastAPI dependencies: the glue between HTTP and the service layer.

A dependency is just a function FastAPI calls for you before your route runs. Its result
is passed into the route. Dependencies can depend on other dependencies, which is how
`get_current_user` gets a DB session and the `*_access` checkers get the current user.

    @router.patch("/tasks/{task_id}")
    async def update_task(access: Access = Depends(task_access(Role.MEMBER))): ...

reads as: "this route needs a logged-in user who is at least a Member of the workspace
that owns task {task_id}". If not, FastAPI returns 401/403/404 and the route never runs.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnauthorizedError
from app.core.redis import get_redis
from app.core.security import decode_token
from app.db.session import get_session
from app.models import Role, User, WorkspaceMember
from app.repositories.users import UserRepository
from app.services.permissions import PermissionService

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]

# auto_error=False: we raise our own 401 with the standard {detail, code} body.
bearer_scheme = HTTPBearer(auto_error=False, description="Paste an access token from /auth/login")


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token", "not_authenticated")
    user_id = decode_token(credentials.credentials, "access")
    user = await UserRepository(session).get(user_id)
    if user is None:
        raise UnauthorizedError("User no longer exists", "invalid_token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass
class Access:
    """Who is calling and with which role, for one workspace."""

    user: User
    member: WorkspaceMember
    workspace_id: int


async def _check(session: AsyncSession, user: User, workspace_id: int, min_role: Role) -> Access:
    member = await PermissionService(session).require_role(workspace_id, user.id, min_role)
    return Access(user=user, member=member, workspace_id=workspace_id)


AccessDep = Callable[..., Awaitable[Access]]


def workspace_access(min_role: Role) -> AccessDep:
    async def dependency(workspace_id: int, user: CurrentUser, session: SessionDep) -> Access:
        return await _check(session, user, workspace_id, min_role)

    return dependency


# The factories below differ only in which path parameter they read. FastAPI matches the
# function parameter name (board_id, task_id, ...) with the {placeholder} in the URL.


def board_access(min_role: Role) -> AccessDep:
    async def dependency(board_id: int, user: CurrentUser, session: SessionDep) -> Access:
        workspace_id = await PermissionService(session).workspace_for("board", board_id)
        return await _check(session, user, workspace_id, min_role)

    return dependency


def column_access(min_role: Role) -> AccessDep:
    async def dependency(column_id: int, user: CurrentUser, session: SessionDep) -> Access:
        workspace_id = await PermissionService(session).workspace_for("column", column_id)
        return await _check(session, user, workspace_id, min_role)

    return dependency


def label_access(min_role: Role) -> AccessDep:
    async def dependency(label_id: int, user: CurrentUser, session: SessionDep) -> Access:
        workspace_id = await PermissionService(session).workspace_for("label", label_id)
        return await _check(session, user, workspace_id, min_role)

    return dependency


def task_access(min_role: Role) -> AccessDep:
    async def dependency(task_id: int, user: CurrentUser, session: SessionDep) -> Access:
        workspace_id = await PermissionService(session).workspace_for("task", task_id)
        return await _check(session, user, workspace_id, min_role)

    return dependency


def comment_access(min_role: Role) -> AccessDep:
    async def dependency(comment_id: int, user: CurrentUser, session: SessionDep) -> Access:
        workspace_id = await PermissionService(session).workspace_for("comment", comment_id)
        return await _check(session, user, workspace_id, min_role)

    return dependency


def attachment_access(min_role: Role) -> AccessDep:
    async def dependency(attachment_id: int, user: CurrentUser, session: SessionDep) -> Access:
        workspace_id = await PermissionService(session).workspace_for("attachment", attachment_id)
        return await _check(session, user, workspace_id, min_role)

    return dependency
