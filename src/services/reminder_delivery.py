"""Delivery loop for due reminders.

This module contains the logic to find reminders that are due, deliver them via a
caller-provided send function, and update the reminder schedule.

The Telegram bot wires this up to python-telegram-bot's JobQueue.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.logging import get_logger
from src.db.models import Conversation, Reminder, User

logger = get_logger(__name__)

SendMessage = Callable[[int, str], Awaitable[None]]


def _advance_next_run_at(
    *,
    current_next_run_at: datetime,
    schedule_type: str,
    now: datetime,
) -> datetime | None:
    if schedule_type == "once":
        return None

    if schedule_type == "daily":
        step = timedelta(days=1)
    elif schedule_type == "weekly":
        step = timedelta(days=7)
    else:
        return None

    next_run_at = current_next_run_at + step
    while next_run_at <= now:
        next_run_at = next_run_at + step

    return next_run_at


async def deliver_due_reminders(
    *,
    session: AsyncSession,
    send_message: SendMessage,
    now: datetime | None = None,
    batch_size: int = 50,
    user_id: int | None = None,
) -> int:
    """Deliver due reminders and update their schedules.

    Returns the number of reminders successfully delivered.

    Notes:
    - Uses row locks (`FOR UPDATE SKIP LOCKED`) to reduce duplicate deliveries
      when multiple workers are running.
    - For repeating reminders, advances `next_run_at` by the schedule interval.
    - For one-time reminders, deactivates them after successful delivery.
    """

    if now is None:
        now = datetime.now(timezone.utc)

    # Prefer the last known chat_id for this user (if present), otherwise fall
    # back to the Telegram user id (works for private chats).
    last_chat_id = (
        select(Conversation.telegram_chat_id)
        .where(Conversation.user_id == User.id)
        .order_by(Conversation.started_at.desc())
        .limit(1)
        .scalar_subquery()
    )

    conditions = [
        Reminder.is_active.is_(True),
        Reminder.next_run_at.is_not(None),
        Reminder.next_run_at <= now,
    ]
    if user_id is not None:
        conditions.append(Reminder.user_id == user_id)

    query = (
        select(Reminder, User.telegram_id, last_chat_id.label("telegram_chat_id"))
        .join(User, User.id == Reminder.user_id)
        .where(*conditions)
        .order_by(Reminder.next_run_at.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )

    result = await session.execute(query)

    delivered = 0
    for reminder, telegram_user_id, telegram_chat_id in result.all():
        chat_id = int(telegram_chat_id or telegram_user_id)

        try:
            await send_message(chat_id, f"⏰ reminder: {reminder.text}")
        except Exception:
            logger.exception(
                "Failed to deliver reminder",
                reminder_id=reminder.id,
                user_id=reminder.user_id,
                chat_id=chat_id,
            )
            continue

        delivered += 1

        if not reminder.next_run_at:
            reminder.is_active = False
            reminder.updated_at = now
            continue

        next_run_at = _advance_next_run_at(
            current_next_run_at=reminder.next_run_at,
            schedule_type=reminder.schedule_type,
            now=now,
        )

        if next_run_at is None:
            reminder.is_active = False
            reminder.next_run_at = None
        else:
            reminder.next_run_at = next_run_at

        reminder.updated_at = now

    return delivered
