"""Goal service.

Provides high-level goal operations built on repositories.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.goal import GoalRepository
from src.db.models import Goal
from src.services.nlp import extract_goal


class GoalService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = GoalRepository(session)

    async def create_from_nl(self, *, user_id: int, message_text: str) -> Goal:
        extraction = await extract_goal(message_text=message_text)
        return await self.repo.create(
            user_id=user_id,
            title=extraction.title,
            description=extraction.description,
        )

    async def create(
        self, *, user_id: int, title: str, description: Optional[str] = None
    ) -> Goal:
        return await self.repo.create(
            user_id=user_id, title=title, description=description
        )
