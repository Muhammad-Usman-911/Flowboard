from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import Access, RedisDep, SessionDep, board_access, task_access
from app.models import Priority, Role
from app.schemas.common import ErrorResponse, Page, PageParams, page_params
from app.schemas.task import TaskCreate, TaskFilters, TaskMove, TaskOut, TaskUpdate
from app.services.tasks import TaskService

router = APIRouter(tags=["tasks"])
PageDep = Annotated[PageParams, Depends(page_params)]


def task_filters(
    assignee_id: Annotated[
        int | None, Query(description="Only tasks assigned to this user")
    ] = None,
    unassigned: Annotated[bool, Query(description="Only tasks without an assignee")] = False,
    priority: Annotated[Priority | None, Query()] = None,
    label_id: Annotated[int | None, Query()] = None,
    column_id: Annotated[int | None, Query()] = None,
    due_before: Annotated[date | None, Query(description="Due on or before (YYYY-MM-DD)")] = None,
    due_after: Annotated[date | None, Query(description="Due on or after (YYYY-MM-DD)")] = None,
    overdue: Annotated[bool, Query(description="Past due and not in a done column")] = False,
    q: Annotated[
        str | None, Query(max_length=100, description="Search title and description")
    ] = None,
) -> TaskFilters:
    return TaskFilters(
        assignee_id=assignee_id,
        unassigned=unassigned,
        priority=priority,
        label_id=label_id,
        column_id=column_id,
        due_before=due_before,
        due_after=due_after,
        overdue=overdue,
        q=q,
    )


@router.post(
    "/boards/{board_id}/tasks",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
    responses={403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def create_task(
    board_id: int,
    data: TaskCreate,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(board_access(Role.MEMBER))],
) -> TaskOut:
    """Create a task (Member+). It is added at the bottom of the column."""
    task = await TaskService(session, redis).create(board_id, data, access.user)
    return TaskOut.model_validate(task)


@router.get(
    "/boards/{board_id}/tasks",
    response_model=Page[TaskOut],
    dependencies=[Depends(board_access(Role.VIEWER))],
)
async def list_tasks(
    board_id: int,
    session: SessionDep,
    redis: RedisDep,
    page: PageDep,
    filters: Annotated[TaskFilters, Depends(task_filters)],
) -> Page[TaskOut]:
    """Tasks of a board ordered by column and position. All filters are optional."""
    items, total = await TaskService(session, redis).search(
        board_id, filters, page.limit, page.offset
    )
    return Page(
        items=[TaskOut.model_validate(t) for t in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/tasks/{task_id}", response_model=TaskOut, dependencies=[Depends(task_access(Role.VIEWER))]
)
async def get_task(task_id: int, session: SessionDep, redis: RedisDep) -> TaskOut:
    return TaskOut.model_validate(await TaskService(session, redis).get(task_id))


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: int,
    data: TaskUpdate,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(task_access(Role.MEMBER))],
) -> TaskOut:
    """Partial update. Only the fields you send change; send `null` to clear
    `due_date` or `assignee_id`."""
    task = await TaskService(session, redis).update(task_id, data, access.user)
    return TaskOut.model_validate(task)


@router.post("/tasks/{task_id}/move", response_model=TaskOut)
async def move_task(
    task_id: int,
    data: TaskMove,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(task_access(Role.MEMBER))],
) -> TaskOut:
    """Move a task to another column and/or position. Positions of the other tasks in
    both columns are updated in the same transaction."""
    task = await TaskService(session, redis).move(task_id, data, access.user)
    return TaskOut.model_validate(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(task_access(Role.MEMBER))],
) -> Response:
    await TaskService(session, redis).delete(task_id, access.user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
