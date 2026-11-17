"""In-app notifications: @mentions in comments and task assignments."""

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Notification, Task, User
from app.repositories.collaboration import NotificationRepository
from app.repositories.users import UserRepository
from app.repositories.workspaces import WorkspaceRepository

# "@" + a username, not preceded by a word character (so emails like a@b.com don't match).
MENTION_RE = re.compile(r"(?<![\w@])@([a-zA-Z0-9_]{3,32})")


def extract_mentions(text: str) -> set[str]:
    return {m.lower() for m in MENTION_RE.findall(text)}


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NotificationRepository(session)
        self.users = UserRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def notify_mentions(
        self, *, text: str, author: User, task: Task, workspace_id: int
    ) -> list[User]:
        """Create a notification for every workspace member mentioned in `text`.
        Does not commit: the caller commits together with the comment."""
        mentioned = await self.users.get_by_usernames(extract_mentions(text))
        member_ids = await self.workspaces.member_user_ids(workspace_id)
        targets = [u for u in mentioned if u.id in member_ids and u.id != author.id]
        await self.repo.add_many(
            [
                Notification(
                    user_id=u.id,
                    type="mention",
                    message=f"@{author.username} mentioned you on '{task.title}'"[:300],
                    task_id=task.id,
                    board_id=task.board_id,
                )
                for u in targets
            ]
        )
        return targets

    async def notify_assigned(self, *, assignee_id: int, actor: User, task: Task) -> None:
        if assignee_id == actor.id:
            return
        await self.repo.add_many(
            [
                Notification(
                    user_id=assignee_id,
                    type="assigned",
                    message=f"@{actor.username} assigned you '{task.title}'"[:300],
                    task_id=task.id,
                    board_id=task.board_id,
                )
            ]
        )

    async def list_for_user(
        self, user: User, unread_only: bool, limit: int, offset: int
    ) -> tuple[list[Notification], int]:
        return await self.repo.list_for_user(user.id, unread_only, limit, offset)

    async def mark_read(self, user: User, notification_id: int) -> Notification:
        notification = await self.repo.get(notification_id)
        if notification is None or notification.user_id != user.id:
            raise NotFoundError("Notification not found")
        notification.is_read = True
        await self.session.commit()
        return notification

    async def mark_all_read(self, user: User) -> int:
        count = await self.repo.mark_all_read(user.id)
        await self.session.commit()
        return count
