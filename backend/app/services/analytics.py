"""Dashboard numbers for a workspace (optionally narrowed to one board)."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.repositories.analytics import AnalyticsRepository
from app.repositories.boards import BoardRepository
from app.schemas.collaboration import AnalyticsOut, MemberCompletion, StatusCount, WeeklyCount
from app.schemas.user import UserPublic


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = AnalyticsRepository(session)
        self.boards = BoardRepository(session)

    async def summary(
        self, workspace_id: int, board_id: int | None = None, weeks: int = 8
    ) -> AnalyticsOut:
        if board_id is not None:
            board = await self.boards.get(board_id)
            if board is None or board.workspace_id != workspace_id:
                raise NotFoundError("Board not found")

        today = datetime.now(UTC).date()
        statuses = await self.repo.tasks_per_status(workspace_id, board_id)
        members = await self.repo.completion_by_member(workspace_id, board_id)

        # Weeks start on Monday (like Postgres date_trunc('week')). Fill empty weeks with 0
        # so the chart has no gaps.
        this_monday = today - timedelta(days=today.weekday())
        first_monday = this_monday - timedelta(weeks=weeks - 1)
        since = datetime.combine(first_monday, datetime.min.time(), tzinfo=UTC)
        per_week = await self.repo.created_per_week(workspace_id, board_id, since)
        week_list: list[date] = [first_monday + timedelta(weeks=i) for i in range(weeks)]

        return AnalyticsOut(
            total_tasks=sum(count for _, _, count in statuses),
            completed_tasks=sum(count for _, done, count in statuses if done),
            overdue_tasks=await self.repo.overdue_count(workspace_id, board_id, today),
            tasks_per_status=[
                StatusCount(title=title, is_done=done, count=count)
                for title, done, count in statuses
            ],
            completion_by_member=[
                MemberCompletion(
                    user=UserPublic.model_validate(user),
                    assigned=assigned,
                    completed=completed,
                    completion_rate=round(completed / assigned, 3) if assigned else 0.0,
                )
                for user, assigned, completed in members
            ],
            tasks_created_per_week=[
                WeeklyCount(week_start=w, count=per_week.get(w, 0)) for w in week_list
            ],
        )
