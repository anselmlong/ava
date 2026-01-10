"""Command handlers for the Telegram bot."""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from src.config.settings import settings
from src.config.logging import get_logger
from src.db import get_session
from src.db.repositories.user import UserRepository
from src.db.models import UserStatus

logger = get_logger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - register or welcome user."""
    if not update.effective_user or not update.message:
        return

    telegram_user = update.effective_user
    logger.info(
        "Start command received",
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
                await update.message.reply_text(
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
                    "/stats - View system statistics"
                )
            else:
                # Create access request
                await repo.create_access_request(
                    telegram_id=telegram_user.id,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name,
                )

                await update.message.reply_text(
                    f"Hello {user.full_name}! 👋\n\n"
                    "Welcome to Ava - your AI personal assistant.\n\n"
                    "Your access request has been submitted and is pending approval. "
                    "An administrator will review your request soon.\n\n"
                    "You'll receive a notification once you're approved."
                )

                # Notify admins
                for admin_id in settings.admin_ids:
                    try:
                        await context.bot.send_message(
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
                await update.message.reply_text(
                    f"Welcome back, {user.full_name}! 👋\n\n"
                    "I'm ready to help. Just send me a message!\n\n"
                    "Commands:\n"
                    "/help - Show available commands\n"
                    "/settings - View your settings"
                )
            elif user.status == UserStatus.PENDING.value:
                await update.message.reply_text(
                    f"Hello {user.full_name}! 👋\n\n"
                    "Your access request is still pending approval. "
                    "Please wait for an administrator to review it."
                )
            elif user.status == UserStatus.SUSPENDED.value:
                await update.message.reply_text(
                    "Your account has been suspended. "
                    "Please contact an administrator for assistance."
                )
            elif user.status == UserStatus.BANNED.value:
                await update.message.reply_text("Your account has been banned.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not update.message:
        return

    help_text = """
*Ava - Your AI Assistant*

*Available Commands:*
/start - Start the bot or check your status
/help - Show this help message
/settings - View and update your settings

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

    await update.message.reply_text(help_text, parse_mode="Markdown")


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command."""
    if not update.effective_user or not update.message:
        return

    async with get_session() as session:
        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(update.effective_user.id)

        if not user:
            await update.message.reply_text(
                "You're not registered yet. Use /start to get started."
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

        await update.message.reply_text(settings_text, parse_mode="Markdown")


# Create handlers
start_handler = CommandHandler("start", start_command)
help_handler = CommandHandler("help", help_command)
settings_handler = CommandHandler("settings", settings_command)
