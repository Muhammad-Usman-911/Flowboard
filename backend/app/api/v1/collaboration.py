from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import (
    Access,
    RedisDep,
    SessionDep,
    attachment_access,
    comment_access,
    task_access,
)
from app.models import Role
from app.schemas.collaboration import AttachmentOut, CommentCreate, CommentOut
from app.schemas.common import ErrorResponse, Page, PageParams, page_params
from app.services.attachments import AttachmentService
from app.services.comments import CommentService

router = APIRouter()
PageDep = Annotated[PageParams, Depends(page_params)]


# --- comments ---
@router.get(
    "/tasks/{task_id}/comments",
    response_model=Page[CommentOut],
    tags=["comments"],
    dependencies=[Depends(task_access(Role.VIEWER))],
)
async def list_comments(
    task_id: int, session: SessionDep, redis: RedisDep, page: PageDep
) -> Page[CommentOut]:
    items, total = await CommentService(session, redis).list_for_task(
        task_id, page.limit, page.offset
    )
    return Page(
        items=[CommentOut.model_validate(c) for c in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "/tasks/{task_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
    tags=["comments"],
)
async def create_comment(
    task_id: int,
    data: CommentCreate,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(task_access(Role.MEMBER))],
) -> CommentOut:
    """Add a comment (Member+). Mention teammates with @username to notify them."""
    comment = await CommentService(session, redis).create(task_id, data, access.user)
    return CommentOut.model_validate(comment)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["comments"])
async def delete_comment(
    comment_id: int,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(comment_access(Role.MEMBER))],
) -> Response:
    """Delete your own comment (Admins can delete any comment)."""
    await CommentService(session, redis).delete(comment_id, access.member)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- attachments ---
@router.get(
    "/tasks/{task_id}/attachments",
    response_model=Page[AttachmentOut],
    tags=["attachments"],
    dependencies=[Depends(task_access(Role.VIEWER))],
)
async def list_attachments(
    task_id: int, session: SessionDep, redis: RedisDep, page: PageDep
) -> Page[AttachmentOut]:
    items, total = await AttachmentService(session, redis).list_for_task(
        task_id, page.limit, page.offset
    )
    return Page(
        items=[AttachmentOut.model_validate(a) for a in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "/tasks/{task_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
    tags=["attachments"],
    responses={
        413: {"model": ErrorResponse, "description": "File larger than 10 MB"},
        415: {"model": ErrorResponse, "description": "File type not allowed"},
    },
)
async def upload_attachment(
    task_id: int,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(task_access(Role.MEMBER))],
    file: Annotated[
        UploadFile, File(description="Max 10 MB: images, PDF, text, CSV, zip, docx, xlsx")
    ],
) -> AttachmentOut:
    attachment = await AttachmentService(session, redis).upload(task_id, file, access.user)
    return AttachmentOut.model_validate(attachment)


@router.get(
    "/attachments/{attachment_id}/download",
    response_class=FileResponse,
    tags=["attachments"],
    dependencies=[Depends(attachment_access(Role.VIEWER))],
)
async def download_attachment(
    attachment_id: int, session: SessionDep, redis: RedisDep
) -> FileResponse:
    attachment, path = await AttachmentService(session, redis).get_file(attachment_id)
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.filename)


@router.delete(
    "/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["attachments"]
)
async def delete_attachment(
    attachment_id: int,
    session: SessionDep,
    redis: RedisDep,
    access: Annotated[Access, Depends(attachment_access(Role.MEMBER))],
) -> Response:
    await AttachmentService(session, redis).delete(attachment_id, access.user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
