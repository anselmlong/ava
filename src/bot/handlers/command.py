"""Command handlers for the Telegram bot."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from src.config.settings import settings


def _format_dt_for_user(dt_utc: datetime, user_timezone: str) -> str:
    """Format a UTC datetime in the user's local timezone."""
    try:
        tz = ZoneInfo(user_timezone)
        local = dt_utc.astimezone(tz)
        return local.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_utc.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


from src.config.logging import get_logger
from src.bot.markdown import reply_markdown, send_markdown
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.db.models import User, UserStatus
from src.db.repositories.conversation import ConversationRepository
from src.db.repositories.goal import GoalRepository
from src.db.repositories.reminder import ReminderRepository
from src.db.repositories.user import UserRepository
from src.services.reminders import ReminderService

logger = get_logger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - register or welcome user."""
    if not update.effective_user or not update.message:
        return

    telegram_user = update.effective_user
    logger.info(
        "Command received",
        update_type="command",
        command="/start",
        telegram_id=telegram_user.id,
        username=telegram_user.username,
    )

    async with get_session() as session:
        repo = UserRepository(session)

        # Check if user is an admin (auto-approve admins)
        is_admin = settings.is_admin(telegram_user.id)

        user, created = await repo.get_or_create(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            language_code=telegram_user.language_code,
            auto_approve=is_admin,
        )

        if created:
            if is_admin:
                await reply_markdown(
                    update.message,
                    f"Welcome, Admin {user.full_name}! 👋\n\n"
                    "You have been automatically approved.\n\n"
                    "I'm Ava, your AI personal assistant. I can help you with:\n"
                    "• Answering questions and having conversations\n"
                    "• Task planning and organization\n"
                    "• Research and information gathering\n\n"
                    "Just send me a message to get started!\n\n"
                    "Admin commands:\n"
                    "/pending - View pending access requests\n"
                    "/approve <telegram_id> - Approve a user\n"
                    "/reject <telegram_id> - Reject a user\n"
                    "/stats - View system statistics",
                )
            else:
                # Create access request
                await repo.create_access_request(
                    telegram_id=telegram_user.id,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name,
                )

                await reply_markdown(
                    update.message,
                    f"Hello {user.full_name}! 👋\n\n"
                    "Welcome to Ava - your AI personal assistant.\n\n"
                    "Your access request has been submitted and is pending approval. "
                    "An administrator will review your request soon.\n\n"
                    "You'll receive a notification once you're approved.",
                )

                # Notify admins
                for admin_id in settings.admin_ids:
                    try:
                        await send_markdown(
                            context.bot,
                            chat_id=admin_id,
                            text=f"🔔 New access request:\n\n"
                            f"Name: {user.full_name}\n"
                            f"Username: @{user.username or 'N/A'}\n"
                            f"Telegram ID: {user.telegram_id}\n\n"
                            f"Use /approve {user.telegram_id} to approve\n"
                            f"Use /reject {user.telegram_id} to reject",
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to notify admin",
                            admin_id=admin_id,
                            error=str(e),
                        )
        else:
            # Existing user
            if user.status == UserStatus.APPROVED.value:
                await reply_markdown(
                    update.message,
                    f"Welcome back, {user.full_name}! 👋\n\n"
                    "I'm ready to help. Just send me a message!\n\n"
                    "Commands:\n"
                    "/help - Show available commands\n"
                    "/settings - View your settings",
                )
            elif user.status == UserStatus.PENDING.value:
                await reply_markdown(
                    update.message,
                    f"Hello {user.full_name}! 👋\n\n"
                    "Your access request is still pending approval. "
                    "Please wait for an administrator to review it.",
                )
            elif user.status == UserStatus.SUSPENDED.value:
                await reply_markdown(
                    update.message,
                    "Your account has been suspended. "
                    "Please contact an administrator for assistance.",
                )
            elif user.status == UserStatus.BANNED.value:
                await reply_markdown(update.message, "Your account has been banned.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not update.message:
        return

    if update.effective_user:
        logger.info(
            "Command received",
            update_type="command",
            command="/help",
            telegram_id=update.effective_user.id,
        )

    help_text = """
*Ava - Your AI Assistant*

*Available Commands:*
/start - Start the bot or check your status
/help - Show this help message
/settings - View and update your settings
/goal add <title> - Add a goal
/goals - List your goals
/remind add <natural language> - Add a reminder
/reminders - List your reminders

*How to use:*
Simply send me a message and I'll respond! I can help with:
• Answering questions
• Having conversations
• Planning and organization
• Research and information

*Tips:*
• Be specific in your questions for better answers
• I remember our conversation context
• Use clear language for best results
"""

    # Add admin commands if user is admin
    if update.effective_user and settings.is_admin(update.effective_user.id):
        help_text += """
*Admin Commands:*
/pending - View pending access requests
/approve <id> - Approve a user
/reject <id> - Reject a user
/stats - View system statistics
"""

    await reply_markdown(update.message, help_text)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command."""
    if not update.effective_user or not update.message:
        return

    async with get_session() as session:
        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(update.effective_user.id)

        if not user:
            await reply_markdown(
                update.message,
                "You're not registered yet. Use /start to get started.",
            )
            return

        settings_text = f"""
*Your Settings*

*Account:*
• Status: {user.status.title()}
• Timezone: {user.timezone}
• Messages sent: {user.message_count}

*Data Retention:*
• Conversation history: {user.conversation_retention_days} days
• Auto-archive: {"Enabled" if user.auto_archive_enabled else "Disabled"}

*Privacy:*
Use /export\\_data to download your data
Use /delete\\_data to delete your account
"""

        if update.effective_user:
            logger.info(
                "Command received",
                update_type="command",
                command="/settings",
                telegram_id=update.effective_user.id,
            )

        await reply_markdown(update.message, settings_text)


async def _get_approved_user(update: Update, session: AsyncSession) -> User | None:
    if not update.effective_user or not update.message:
        return None

    repo = UserRepository(session)
    user = await repo.get_by_telegram_id(update.effective_user.id)

    if not user:
        await reply_markdown(
            update.message,
            "You're not registered yet. Use /start to get started.",
        )
        return None

    if user.status != UserStatus.APPROVED.value:
        if user.status == UserStatus.PENDING.value:
            await reply_markdown(
                update.message, "Your access is still pending approval."
            )
        elif user.status == UserStatus.SUSPENDED.value:
            await reply_markdown(update.message, "Your account is suspended.")
        elif user.status == UserStatus.BANNED.value:
            await reply_markdown(update.message, "Your account is banned.")
        return None

    return user


async def goal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /goal command."""
    if not update.message:
        return

    if not context.args or context.args[0] != "add":
        await reply_markdown(update.message, "Usage: /goal add <title>")
        return

    title = " ".join(context.args[1:]).strip()
    if not title:
        await reply_markdown(update.message, "Usage: /goal add <title>")
        return

    async with get_session() as session:
        user = await _get_approved_user(update, session)
        if user is None:
            return

        goal_repo = GoalRepository(session)
        goal = await goal_repo.create(user_id=user.id, title=title)

        await reply_markdown(update.message, f"✅ added goal: *{goal.title}*")


async def goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /goals command."""
    if not update.message:
        return

    async with get_session() as session:
        user = await _get_approved_user(update, session)
        if user is None:
            return

        goal_repo = GoalRepository(session)
        goals = await goal_repo.list_for_user(user_id=user.id, include_inactive=True)

        if not goals:
            await reply_markdown(update.message, "you don’t have any goals yet.")
            return

        lines = ["*Your goals:*", ""]
        for goal in goals[:20]:
            lines.append(f"• *{goal.title}* — {goal.status}")

        await reply_markdown(update.message, "\n".join(lines))


async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /remind command."""
    if not update.message:
        return

    if not context.args or context.args[0] != "add":
        await reply_markdown(update.message, "Usage: /remind add <natural language>")
        return

    nl = " ".join(context.args[1:]).strip()
    if not nl:
        await reply_markdown(update.message, "Usage: /remind add <natural language>")
        return

    # Make it explicit for the extractor.
    message_text = nl if "remind" in nl.lower() else f"remind me {nl}"

    async with get_session() as session:
        user = await _get_approved_user(update, session)
        if user is None:
            return

        chat_id = (
            update.effective_chat.id if update.effective_chat else user.telegram_id
        )
        conv_repo = ConversationRepository(session)
        conversation, _ = await conv_repo.get_or_create_active(
            user_id=user.id,
            telegram_chat_id=chat_id,
        )

        reminder_service = ReminderService(session)
        result = await reminder_service.create_from_nl(
            user_id=user.id,
            conversation_id=conversation.id,
            message_text=message_text,
            user_timezone=user.timezone,
        )

        if result.clarification_question:
            await reply_markdown(update.message, result.clarification_question)
            return

        reminder = result.reminder
        if reminder and reminder.next_run_at:
            when = _format_dt_for_user(reminder.next_run_at, user.timezone)
            await reply_markdown(
                update.message,
                f"✅ ok. reminder saved for {when}: {reminder.text}",
            )
        else:
            await reply_markdown(update.message, "✅ ok. reminder saved.")


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reminders command."""
    if not update.message:
        return

    async with get_session() as session:
        user = await _get_approved_user(update, session)
        if user is None:
            return

        reminder_repo = ReminderRepository(session)
        reminders = await reminder_repo.list_for_user(
            user_id=user.id,
            include_inactive=True,
        )

        if not reminders:
            await reply_markdown(update.message, "you don’t have any reminders yet.")
            return

        lines = ["*Your reminders:*", ""]
        for reminder in reminders[:20]:
            status = "active" if reminder.is_active else "inactive"
            when = (
                _format_dt_for_user(reminder.next_run_at, user.timezone)
                if reminder.next_run_at
                else "(unscheduled)"
            )
            lines.append(f"• {when} — {status} — {reminder.text}")

        await reply_markdown(update.message, "\n".join(lines))


# Create handlers
start_handler = CommandHandler("start", start_command)
help_handler = CommandHandler("help", help_command)
settings_handler = CommandHandler("settings", settings_command)
goal_handler = CommandHandler("goal", goal_command)
goals_handler = CommandHandler("goals", goals_command)
remind_handler = CommandHandler("remind", remind_command)
reminders_handler = CommandHandler("reminders", reminders_command)
