"""Reminder repository for database operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Reminder, ReminderScheduleType


class ReminderRepository:
    """Repository for Reminder-related database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        user_id: int,
        text: str,
        schedule_text: str,
        schedule_type: str = ReminderScheduleType.ONCE.value,
        next_run_at: Optional[datetime] = None,
        goal_id: Optional[int] = None,
    ) -> Reminder:
        reminder = Reminder(
            user_id=user_id,
            goal_id=goal_id,
            text=text,
            schedule_text=schedule_text,
            schedule_type=schedule_type,
            next_run_at=next_run_at,
            is_active=True,
        )
        self.session.add(reminder)
        await self.session.flush()
        return reminder

    async def get_by_id(self, *, reminder_id: int, user_id: int) -> Optional[Reminder]:
        result = await self.session.execute(
            select(Reminder).where(
                Reminder.id == reminder_id, Reminder.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        *,
        user_id: int,
        include_inactive: bool = False,
        limit: int = 50,
    ) -> List[Reminder]:
        query = select(Reminder).where(Reminder.user_id == user_id)
        if not include_inactive:
            query = query.where(Reminder.is_active.is_(True))
        query = query.order_by(Reminder.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def deactivate(
        self,
        *,
        reminder_id: int,
        user_id: int,
    ) -> Optional[Reminder]:
        reminder = await self.get_by_id(reminder_id=reminder_id, user_id=user_id)
        if not reminder:
            return None

        reminder.is_active = False
        reminder.updated_at = datetime.now(timezone.utc)
        return reminder
