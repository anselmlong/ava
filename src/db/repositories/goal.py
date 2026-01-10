"""Goal repository for database operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Goal, GoalStatus


class GoalRepository:
    """Repository for Goal-related database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        user_id: int,
        title: str,
        description: Optional[str] = None,
    ) -> Goal:
        goal = Goal(
            user_id=user_id,
            title=title,
            description=description,
            status=GoalStatus.ACTIVE.value,
        )
        self.session.add(goal)
        await self.session.flush()
        return goal

    async def get_by_id(self, *, goal_id: int, user_id: int) -> Optional[Goal]:
        result = await self.session.execute(
            select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        *,
        user_id: int,
        include_inactive: bool = False,
        limit: int = 50,
    ) -> List[Goal]:
        query = select(Goal).where(Goal.user_id == user_id)
        if not include_inactive:
            query = query.where(Goal.status == GoalStatus.ACTIVE.value)
        query = query.order_by(Goal.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def set_status(
        self,
        *,
        goal_id: int,
        user_id: int,
        status: str,
    ) -> Optional[Goal]:
        goal = await self.get_by_id(goal_id=goal_id, user_id=user_id)
        if not goal:
            return None

        goal.status = status
        goal.updated_at = datetime.now(timezone.utc)
        return goal
