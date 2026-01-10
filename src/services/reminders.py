"""Reminder service.

Handles natural-language extraction and normalization into schedulable reminders.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Any

from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.reminder import ReminderRepository
from src.db.repositories.conversation import ConversationRepository
from src.db.models import Reminder
from src.services.nlp import (
    extract_reminder,
    extract_time_followup,
    parse_iso_datetime,
)


@dataclass(frozen=True)
class ReminderCreateResult:
    reminder: Optional[Reminder]
    clarification_question: Optional[str]
    pending_action: Optional[dict[str, Any]]


class ReminderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ReminderRepository(session)
        self.conv_repo = ConversationRepository(session)

    async def create_from_nl(
        self,
        *,
        user_id: int,
        conversation_id: int,
        message_text: str,
        user_timezone: str,
    ) -> ReminderCreateResult:
        tz = ZoneInfo(user_timezone)
        now_local_iso = datetime.now(timezone.utc).astimezone(tz).isoformat()

        extraction = await extract_reminder(
            message_text=message_text,
            user_timezone=user_timezone,
            now_local_iso=now_local_iso,
        )

        if extraction.needs_clarification:
            pending_action = {
                "type": "create_reminder",
                "awaiting": "time",
                "draft": {
                    "text": extraction.text,
                    "schedule_text": extraction.schedule_text,
                    "schedule_type": extraction.schedule_type,
                    "date_local_iso": extraction.date_local_iso,
                },
            }

            conversation = await self.conv_repo.get_by_id(conversation_id)
            if conversation:
                existing = dict(conversation.context or {})
                existing["pending_action"] = pending_action
                conversation.context = existing

            return ReminderCreateResult(
                reminder=None,
                clarification_question=extraction.clarification_question
                or "what time?",
                pending_action=pending_action,
            )

        if not extraction.next_run_at_local:
            raise ValueError("Reminder extraction missing next_run_at_local")

        next_local = parse_iso_datetime(extraction.next_run_at_local)
        next_utc = next_local.astimezone(timezone.utc)

        reminder = await self.repo.create(
            user_id=user_id,
            text=extraction.text,
            schedule_text=extraction.schedule_text,
            schedule_type=extraction.schedule_type,
            next_run_at=next_utc,
        )

        await self.conv_repo.clear_pending_action(conversation_id=conversation_id)

        return ReminderCreateResult(
            reminder=reminder, clarification_question=None, pending_action=None
        )

    async def continue_from_time_followup(
        self,
        *,
        user_id: int,
        conversation_id: int,
        message_text: str,
        user_timezone: str,
        draft: dict[str, Any],
    ) -> ReminderCreateResult:
        date_local_iso = draft.get("date_local_iso")
        if not isinstance(date_local_iso, str) or not date_local_iso:
            # Without a date, we can't safely continue.
            await self.conv_repo.clear_pending_action(conversation_id=conversation_id)
            return ReminderCreateResult(
                reminder=None,
                clarification_question="sorry—what day should i remind you?",
                pending_action=None,
            )

        extraction = await extract_time_followup(
            message_text=message_text,
            user_timezone=user_timezone,
            date_local_iso=date_local_iso,
        )

        if extraction.needs_clarification or not extraction.next_run_at_local:
            return ReminderCreateResult(
                reminder=None,
                clarification_question=extraction.clarification_question
                or "what time?",
                pending_action=draft,
            )

        next_local = parse_iso_datetime(extraction.next_run_at_local)
        next_utc = next_local.astimezone(timezone.utc)

        reminder = await self.repo.create(
            user_id=user_id,
            text=str(draft.get("text") or ""),
            schedule_text=str(draft.get("schedule_text") or ""),
            schedule_type=str(draft.get("schedule_type") or "once"),
            next_run_at=next_utc,
        )

        await self.conv_repo.clear_pending_action(conversation_id=conversation_id)

        return ReminderCreateResult(
            reminder=reminder, clarification_question=None, pending_action=None
        )
