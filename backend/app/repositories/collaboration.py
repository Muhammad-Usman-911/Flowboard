from sqlalchemy import select, update

from app.models import ActivityLog, Attachment, Comment, Notification
from app.repositories.base import BaseRepository


class CommentRepository(BaseRepository):
    async def get(self, comment_id: int) -> Comment | None:
        return await self.session.get(Comment, comment_id)

    async def add(self, comment: Comment) -> Comment:
        self.session.add(comment)
        await self.session.flush()
        await self.session.refresh(comment, attribute_names=["author", "created_at"])
        return comment

    async def delete(self, comment: Comment) -> None:
        await self.session.delete(comment)
        await self.session.flush()

    async def list_for_task(
        self, task_id: int, limit: int, offset: int
    ) -> tuple[list[Comment], int]:
        stmt = (
            select(Comment)
            .where(Comment.task_id == task_id)
            .order_by(Comment.created_at, Comment.id)
        )
        return await self.paginate(stmt, limit, offset)


class AttachmentRepository(BaseRepository):
    async def get(self, attachment_id: int) -> Attachment | None:
        return await self.session.get(Attachment, attachment_id)

    async def add(self, attachment: Attachment) -> Attachment:
        self.session.add(attachment)
        await self.session.flush()
        await self.session.refresh(attachment, attribute_names=["created_at"])
        return attachment

    async def delete(self, attachment: Attachment) -> None:
        await self.session.delete(attachment)
        await self.session.flush()

    async def list_for_task(
        self, task_id: int, limit: int, offset: int
    ) -> tuple[list[Attachment], int]:
        stmt = (
            select(Attachment)
            .where(Attachment.task_id == task_id)
            .order_by(Attachment.created_at, Attachment.id)
        )
        return await self.paginate(stmt, limit, offset)

    async def stored_names_for_tasks(self, task_ids: list[int]) -> list[str]:
        if not task_ids:
            return []
        stmt = select(Attachment.stored_name).where(Attachment.task_id.in_(task_ids))
        return list((await self.session.execute(stmt)).scalars().all())


class NotificationRepository(BaseRepository):
    async def add_many(self, notifications: list[Notification]) -> None:
        self.session.add_all(notifications)
        await self.session.flush()

    async def get(self, notification_id: int) -> Notification | None:
        return await self.session.get(Notification, notification_id)

    async def list_for_user(
        self, user_id: int, unread_only: bool, limit: int, offset: int
    ) -> tuple[list[Notification], int]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
        stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
        return await self.paginate(stmt, limit, offset)

    async def mark_all_read(self, user_id: int) -> int:
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
        result = await self.session.execute(stmt)
        return result.rowcount  # type: ignore[attr-defined]


class ActivityRepository(BaseRepository):
    async def add(self, entry: ActivityLog) -> ActivityLog:
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list_entries(
        self,
        workspace_id: int,
        board_id: int | None,
        task_id: int | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ActivityLog], int]:
        stmt = select(ActivityLog).where(ActivityLog.workspace_id == workspace_id)
        if board_id is not None:
            stmt = stmt.where(ActivityLog.board_id == board_id)
        if task_id is not None:
            stmt = stmt.where(ActivityLog.task_id == task_id)
        stmt = stmt.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        return await self.paginate(stmt, limit, offset)
