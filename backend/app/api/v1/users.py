from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, SessionDep
from app.schemas.collaboration import NotificationOut
from app.schemas.common import Message, Page, PageParams, page_params
from app.schemas.user import UserMe, UserUpdate
from app.services.auth import AuthService
from app.services.notifications import NotificationService

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=UserMe)
async def read_me(user: CurrentUser) -> UserMe:
    """The logged-in user's profile."""
    return UserMe.model_validate(user)


@router.patch("/users/me", response_model=UserMe)
async def update_me(data: UserUpdate, user: CurrentUser, session: SessionDep) -> UserMe:
    """Change your display name and/or password."""
    return UserMe.model_validate(await AuthService(session).update_profile(user, data))


@router.get("/notifications", response_model=Page[NotificationOut], tags=["notifications"])
async def list_notifications(
    user: CurrentUser,
    session: SessionDep,
    page: Annotated[PageParams, Depends(page_params)],
    unread_only: Annotated[bool, Query()] = False,
) -> Page[NotificationOut]:
    """Your notifications, newest first (mentions and assignments)."""
    items, total = await NotificationService(session).list_for_user(
        user, unread_only, page.limit, page.offset
    )
    return Page(
        items=[NotificationOut.model_validate(n) for n in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "/notifications/{notification_id}/read", response_model=NotificationOut, tags=["notifications"]
)
async def mark_notification_read(
    notification_id: int, user: CurrentUser, session: SessionDep
) -> NotificationOut:
    notification = await NotificationService(session).mark_read(user, notification_id)
    return NotificationOut.model_validate(notification)


@router.post("/notifications/read-all", response_model=Message, tags=["notifications"])
async def mark_all_notifications_read(user: CurrentUser, session: SessionDep) -> Message:
    count = await NotificationService(session).mark_all_read(user)
    return Message(message=f"Marked {count} notifications as read")
