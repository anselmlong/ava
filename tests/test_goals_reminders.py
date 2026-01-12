"""Tests for Phase 3(A): goals and reminders."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.db.repositories.conversation import ConversationRepository
from src.db.repositories.goal import GoalRepository
from src.db.repositories.reminder import ReminderRepository
from src.db.repositories.user import UserRepository
from src.services.reminders import ReminderService
from src.services.reminder_delivery import deliver_due_reminders
from src.services.nlp import ReminderExtraction, TimeFollowupExtraction


@pytest.fixture
async def test_user(session):
    repo = UserRepository(session)
    user, _ = await repo.get_or_create(
        telegram_id=999001,
        username="testuser",
        first_name="Test",
        auto_approve=True,
    )
    await session.commit()
    return user


@pytest.fixture
async def test_conversation(session, test_user):
    repo = ConversationRepository(session)
    conversation, _ = await repo.get_or_create_active(
        user_id=test_user.id,
        telegram_chat_id=test_user.telegram_id,
    )
    await session.commit()
    return conversation


async def test_goal_repository_create_and_list(session, test_user):
    repo = GoalRepository(session)

    created = await repo.create(user_id=test_user.id, title="run a 5k")
    await session.commit()

    assert created.id is not None
    assert created.title == "run a 5k"

    goals = await repo.list_for_user(user_id=test_user.id, include_inactive=True)
    assert any(goal.id == created.id for goal in goals)


async def test_reminder_repository_create_and_list(session, test_user):
    repo = ReminderRepository(session)

    created = await repo.create(
        user_id=test_user.id,
        text="call mom",
        schedule_text="tomorrow at 3pm",
        schedule_type="once",
        next_run_at=datetime.now(timezone.utc),
    )
    await session.commit()

    assert created.id is not None
    reminders = await repo.list_for_user(user_id=test_user.id, include_inactive=True)
    assert any(reminder.id == created.id for reminder in reminders)


async def test_reminder_service_sets_pending_action_on_missing_time(
    session, test_user, test_conversation
):
    service = ReminderService(session)

    mock_extraction = ReminderExtraction(
        text="call mom",
        schedule_text="tomorrow",
        schedule_type="once",
        date_local_iso="2026-01-11",
        next_run_at_local=None,
        needs_clarification=True,
        clarification_question="what time tomorrow?",
    )

    with patch(
        "src.services.reminders.extract_reminder",
        new=AsyncMock(return_value=mock_extraction),
    ):
        result = await service.create_from_nl(
            user_id=test_user.id,
            conversation_id=test_conversation.id,
            message_text="remind me tomorrow to call mom",
            user_timezone="UTC",
        )

    assert result.reminder is None
    assert result.clarification_question == "what time tomorrow?"

    # Context should have pending_action.
    conv_repo = ConversationRepository(session)
    refreshed = await conv_repo.get_by_id(test_conversation.id)
    assert refreshed is not None
    assert "pending_action" in (refreshed.context or {})


async def test_reminder_service_creates_from_followup_time(
    session, test_user, test_conversation
):
    service = ReminderService(session)

    # Seed a pending_action draft.
    conv_repo = ConversationRepository(session)
    conversation = await conv_repo.get_by_id(test_conversation.id)
    assert conversation is not None
    conversation.context = {
        "pending_action": {
            "type": "create_reminder",
            "awaiting": "time",
            "draft": {
                "text": "call mom",
                "schedule_text": "tomorrow",
                "schedule_type": "once",
                "date_local_iso": "2026-01-11",
            },
        }
    }
    await session.commit()

    mock_time = TimeFollowupExtraction(
        next_run_at_local="2026-01-11T15:00:00+00:00",
        needs_clarification=False,
        clarification_question=None,
    )

    with patch(
        "src.services.reminders.extract_time_followup",
        new=AsyncMock(return_value=mock_time),
    ):
        result = await service.continue_from_time_followup(
            user_id=test_user.id,
            conversation_id=test_conversation.id,
            message_text="3pm",
            user_timezone="UTC",
            draft={
                "text": "call mom",
                "schedule_text": "tomorrow",
                "schedule_type": "once",
                "date_local_iso": "2026-01-11",
            },
        )

    assert result.reminder is not None
    assert result.reminder.text == "call mom"

    refreshed = await conv_repo.get_by_id(test_conversation.id)
    assert refreshed is not None
    assert "pending_action" not in (refreshed.context or {})


async def test_deliver_due_once_reminder_deactivates(session):
    user_repo = UserRepository(session)
    user, _ = await user_repo.get_or_create(
        telegram_id=999101,
        username="reminder_once",
        first_name="Reminder",
        auto_approve=True,
    )

    repo = ReminderRepository(session)
    now = datetime.now(timezone.utc)

    created = await repo.create(
        user_id=user.id,
        text="call mom",
        schedule_text="in 1 second",
        schedule_type="once",
        next_run_at=now - timedelta(seconds=1),
    )
    await session.commit()

    send_message = AsyncMock()
    delivered = await deliver_due_reminders(
        session=session,
        send_message=send_message,
        now=now,
        user_id=user.id,
    )
    await session.commit()

    assert delivered == 1
    send_message.assert_awaited()

    refreshed = await repo.get_by_id(reminder_id=created.id, user_id=user.id)
    assert refreshed is not None
    assert refreshed.is_active is False
    assert refreshed.next_run_at is None


async def test_deliver_due_daily_reminder_advances_next_run(session):
    user_repo = UserRepository(session)
    user, _ = await user_repo.get_or_create(
        telegram_id=999102,
        username="reminder_daily",
        first_name="Reminder",
        auto_approve=True,
    )

    repo = ReminderRepository(session)
    now = datetime.now(timezone.utc)

    created = await repo.create(
        user_id=user.id,
        text="drink water",
        schedule_text="daily",
        schedule_type="daily",
        next_run_at=now - timedelta(days=2),
    )
    await session.commit()

    send_message = AsyncMock()
    delivered = await deliver_due_reminders(
        session=session,
        send_message=send_message,
        now=now,
        user_id=user.id,
    )
    await session.commit()

    assert delivered == 1

    refreshed = await repo.get_by_id(reminder_id=created.id, user_id=user.id)
    assert refreshed is not None
    assert refreshed.is_active is True
    assert refreshed.next_run_at is not None
    assert refreshed.next_run_at > now
