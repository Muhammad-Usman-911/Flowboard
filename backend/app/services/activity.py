"""Writes activity log entries. The entry is added to the *same* session as the change
it describes, so both are committed (or rolled back) together."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActivityLog
from app.repositories.collaboration import ActivityRepository


class ActivityService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = ActivityRepository(session)

    async def record(
        self,
        *,
        workspace_id: int,
        user_id: int | None,
        action: str,
        summary: str,
        board_id: int | None = None,
        task_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> ActivityLog:
        return await self.repo.add(
            ActivityLog(
                workspace_id=workspace_id,
                user_id=user_id,
                action=action,
                summary=summary[:300],
                board_id=board_id,
                task_id=task_id,
                details=details or {},
            )
        )

    async def list_entries(
        self, workspace_id: int, board_id: int | None, task_id: int | None, limit: int, offset: int
    ) -> tuple[list[ActivityLog], int]:
        return await self.repo.list_entries(workspace_id, board_id, task_id, limit, offset)
