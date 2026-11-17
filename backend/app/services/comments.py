"""Task comments (with @mentions -> notifications)."""

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.models import Comment, Role, User, WorkspaceMember
from app.realtime.events import EventPublisher
from app.repositories.boards import BoardRepository
from app.repositories.collaboration import CommentRepository
from app.repositories.tasks import TaskRepository
from app.schemas.collaboration import CommentCreate, CommentOut
from app.services.activity import ActivityService
from app.services.notifications import NotificationService


class CommentService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self.session = session
        self.repo = CommentRepository(session)
        self.tasks = TaskRepository(session)
        self.boards = BoardRepository(session)
        self.activity = ActivityService(session)
        self.notifications = NotificationService(session)
        self.events = EventPublisher(redis)

    async def list_for_task(
        self, task_id: int, limit: int, offset: int
    ) -> tuple[list[Comment], int]:
        return await self.repo.list_for_task(task_id, limit, offset)

    async def create(self, task_id: int, data: CommentCreate, actor: User) -> Comment:
        task = await self.tasks.get(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        board = await self.boards.get(task.board_id)
        assert board is not None
        comment = await self.repo.add(Comment(task_id=task_id, author_id=actor.id, body=data.body))
        mentioned = await self.notifications.notify_mentions(
            text=data.body, author=actor, task=task, workspace_id=board.workspace_id
        )
        await self.activity.record(
            workspace_id=board.workspace_id,
            user_id=actor.id,
            board_id=board.id,
            task_id=task.id,
            action="comment.created",
            summary=f"commented on '{task.title}'",
            details={"comment_id": comment.id, "mentioned": [u.username for u in mentioned]},
        )
        await self.session.commit()
        payload = CommentOut.model_validate(comment).model_dump(mode="json")
        await self.events.publish(board.id, "comment.created", payload, actor.id)
        return comment

    async def delete(self, comment_id: int, actor: WorkspaceMember) -> None:
        comment = await self.repo.get(comment_id)
        if comment is None:
            raise NotFoundError("Comment not found")
        if comment.author_id != actor.user_id and not actor.role.at_least(Role.ADMIN):
            raise ForbiddenError("You can only delete your own comments", "not_author")
        task = await self.tasks.get(comment.task_id)
        assert task is not None
        await self.repo.delete(comment)
        await self.session.commit()
        await self.events.publish(
            task.board_id,
            "comment.deleted",
            {"id": comment_id, "task_id": task.id},
            actor.user_id,
        )
