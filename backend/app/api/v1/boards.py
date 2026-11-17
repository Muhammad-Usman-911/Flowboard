from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import (
    Access,
    RedisDep,
    SessionDep,
    board_access,
    column_access,
    label_access,
    workspace_access,
)
from app.models import Role
from app.schemas.board import (
    BoardCreate,
    BoardDetail,
    BoardOut,
    BoardUpdate,
    ColumnCreate,
    ColumnOut,
    ColumnUpdate,
    LabelCreate,
    LabelOut,
)
from app.schemas.common import Page, PageParams, page_params
from app.services.boards import BoardService

router = APIRouter(tags=["boards"])
PageDep = Annotated[PageParams, Depends(page_params)]


@router.post(
    "/workspaces/{workspace_id}/boards",
    response_model=BoardOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_board(
    workspace_id: int,
    data: BoardCreate,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(workspace_access(Role.ADMIN))],
) -> BoardOut:
    """Create a board with starting columns (Admin+). The last column is the "done" one."""
    board = await BoardService(session, redis).create(workspace_id, data, access.user)
    return BoardOut.model_validate(board)


@router.get(
    "/workspaces/{workspace_id}/boards",
    response_model=Page[BoardOut],
    dependencies=[Depends(workspace_access(Role.VIEWER))],
)
async def list_boards(
    workspace_id: int, session: SessionDep, redis: RedisDep, page: PageDep
) -> Page[BoardOut]:
    items, total = await BoardService(session, redis).list_boards(
        workspace_id, page.limit, page.offset
    )
    return Page(
        items=[BoardOut.model_validate(b) for b in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/boards/{board_id}",
    response_model=BoardDetail,
    dependencies=[Depends(board_access(Role.VIEWER))],
)
async def get_board(board_id: int, session: SessionDep, redis: RedisDep) -> BoardDetail:
    """A board with its ordered columns and its labels."""
    return await BoardService(session, redis).detail(board_id)


@router.patch("/boards/{board_id}", response_model=BoardOut)
async def update_board(
    board_id: int,
    data: BoardUpdate,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(board_access(Role.ADMIN))],
) -> BoardOut:
    board = await BoardService(session, redis).update(board_id, data, access.user)
    return BoardOut.model_validate(board)


@router.delete("/boards/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_board(
    board_id: int,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(board_access(Role.ADMIN))],
) -> Response:
    await BoardService(session, redis).delete(board_id, access.user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- columns ---
@router.post(
    "/boards/{board_id}/columns", response_model=ColumnOut, status_code=status.HTTP_201_CREATED
)
async def create_column(
    board_id: int,
    data: ColumnCreate,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(board_access(Role.ADMIN))],
) -> ColumnOut:
    column = await BoardService(session, redis).add_column(board_id, data, access.user)
    return ColumnOut.model_validate(column)


@router.patch("/columns/{column_id}", response_model=ColumnOut)
async def update_column(
    column_id: int,
    data: ColumnUpdate,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(column_access(Role.ADMIN))],
) -> ColumnOut:
    """Rename a column, mark it as "done", or move it (send `position`)."""
    column = await BoardService(session, redis).update_column(column_id, data, access.user)
    return ColumnOut.model_validate(column)


@router.delete("/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_column(
    column_id: int,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(column_access(Role.ADMIN))],
) -> Response:
    """Delete an empty column (409 if it still has tasks or is the last column)."""
    await BoardService(session, redis).delete_column(column_id, access.user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- labels ---
@router.get(
    "/boards/{board_id}/labels",
    response_model=Page[LabelOut],
    dependencies=[Depends(board_access(Role.VIEWER))],
)
async def list_labels(
    board_id: int, session: SessionDep, redis: RedisDep, page: PageDep
) -> Page[LabelOut]:
    items, total = await BoardService(session, redis).list_labels(board_id, page.limit, page.offset)
    return Page(
        items=[LabelOut.model_validate(label) for label in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "/boards/{board_id}/labels", response_model=LabelOut, status_code=status.HTTP_201_CREATED
)
async def create_label(
    board_id: int,
    data: LabelCreate,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(board_access(Role.MEMBER))],
) -> LabelOut:
    label = await BoardService(session, redis).add_label(board_id, data, access.user)
    return LabelOut.model_validate(label)


@router.delete("/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_label(
    label_id: int,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(label_access(Role.ADMIN))],
) -> Response:
    await BoardService(session, redis).delete_label(label_id, access.user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
