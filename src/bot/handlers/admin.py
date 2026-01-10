"""Admin command handlers."""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from src.config.settings import settings
from src.config.logging import get_logger
from src.bot.markdown import reply_markdown, send_markdown
from src.db import get_session
from src.db.repositories.user import UserRepository
from src.db.models import UserStatus

logger = get_logger(__name__)


def admin_required(func):
    """Decorator to require admin privileges."""

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user:
            return

        if not settings.is_admin(update.effective_user.id):
            if update.message:
                await reply_markdown(
                    update.message,
                    "This command is only available to administrators.",
                )
            return

        return await func(update, context)

    return wrapper


@admin_required
async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /approve command - approve a user."""
    if not update.message or not update.effective_user:
        return

    logger.info(
        "Command received",
        update_type="command",
        command="/approve",
        telegram_id=update.effective_user.id,
    )

    if not context.args or len(context.args) < 1:
        await reply_markdown(
            update.message,
            "Usage: /approve <telegram_id>\n\nUse /pending to see pending requests.",
        )
        return

    try:
        target_telegram_id = int(context.args[0])
    except ValueError:
        await reply_markdown(
            update.message,
            "Invalid Telegram ID. Please provide a number.",
        )
        return

    async with get_session() as session:
        repo = UserRepository(session)

        # Get admin user
        admin_user = await repo.get_by_telegram_id(update.effective_user.id)
        admin_id = admin_user.id if admin_user else None

        # Approve the user
        user = await repo.approve_by_telegram_id(
            telegram_id=target_telegram_id,
            approved_by=admin_id,
        )

        if not user:
            await reply_markdown(
                update.message,
                f"User with Telegram ID {target_telegram_id} not found.",
            )
            return

        if user.status != UserStatus.APPROVED.value:
            await reply_markdown(
                update.message,
                f"Failed to approve user {user.full_name}.",
            )
            return

        # Mark latest access request as approved (if present)
        request = await repo.get_access_request_by_telegram_id(target_telegram_id)
        if request and request.is_pending:
            await repo.approve_access_request(request.id, reviewed_by=admin_id)

        await reply_markdown(
            update.message,
            f"✅ User approved successfully!\n\n"
            f"Name: {user.full_name}\n"
            f"Username: @{user.username or 'N/A'}\n"
            f"Telegram ID: {user.telegram_id}",
        )

        # Notify the user
        try:
            await send_markdown(
                context.bot,
                chat_id=target_telegram_id,
                text="🎉 Your access request has been approved!\n\n"
                "Welcome to Ava! You can now start chatting with me.\n"
                "Just send a message to get started.\n\n"
                "Use /help to see available commands.",
            )
        except Exception as e:
            logger.warning(
                "Failed to notify approved user",
                telegram_id=target_telegram_id,
                error=str(e),
            )

        logger.info(
            "User approved",
            approved_telegram_id=target_telegram_id,
            admin_telegram_id=update.effective_user.id,
            admin_user_id=admin_id,
        )


@admin_required
async def reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reject command - reject a user."""
    if not update.message or not update.effective_user:
        return

    logger.info(
        "Command received",
        update_type="command",
        command="/reject",
        telegram_id=update.effective_user.id,
    )

    if not context.args or len(context.args) < 1:
        await reply_markdown(
            update.message,
            "Usage: /reject <telegram_id> [reason]\n\n"
            "Use /pending to see pending requests.",
        )
        return

    try:
        target_telegram_id = int(context.args[0])
    except ValueError:
        await reply_markdown(
            update.message,
            "Invalid Telegram ID. Please provide a number.",
        )
        return

    reason = " ".join(context.args[1:]) if len(context.args) > 1 else None

    async with get_session() as session:
        repo = UserRepository(session)

        # Get admin user
        admin_user = await repo.get_by_telegram_id(update.effective_user.id)
        admin_id = admin_user.id if admin_user else None

        # Get the user
        user = await repo.get_by_telegram_id(target_telegram_id)
        if not user:
            await reply_markdown(
                update.message,
                f"User with Telegram ID {target_telegram_id} not found.",
            )
            return

        # Ban the user (rejection = ban for now)
        await repo.ban(user.id)

        # Mark latest access request as rejected (if present)
        request = await repo.get_access_request_by_telegram_id(target_telegram_id)
        if request and request.is_pending:
            await repo.reject_access_request(
                request.id,
                reviewed_by=admin_id,
                rejection_reason=reason,
            )

        await reply_markdown(
            update.message,
            f"❌ User rejected.\n\n"
            f"Name: {user.full_name}\n"
            f"Username: @{user.username or 'N/A'}\n"
            f"Telegram ID: {user.telegram_id}"
            + (f"\nReason: {reason}" if reason else ""),
        )

        # Notify the user
        try:
            message = "Your access request has been reviewed and unfortunately cannot be approved at this time."
            if reason:
                message += f"\n\nReason: {reason}"
            await send_markdown(
                context.bot,
                chat_id=target_telegram_id,
                text=message,
            )
        except Exception as e:
            logger.warning(
                "Failed to notify rejected user",
                telegram_id=target_telegram_id,
                error=str(e),
            )

        logger.info(
            "User rejected",
            rejected_telegram_id=target_telegram_id,
            admin_telegram_id=update.effective_user.id,
            admin_user_id=admin_id,
            reason=reason,
        )


@admin_required
async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pending command - list pending access requests."""
    if not update.message:
        return

    async with get_session() as session:
        repo = UserRepository(session)

        pending_users = await repo.get_pending_users()

        logger.info(
            "Command received",
            update_type="command",
            command="/pending",
            telegram_id=update.effective_user.id if update.effective_user else None,
        )

        if not pending_users:
            await reply_markdown(update.message, "No pending access requests.")
            return

        text = f"📋 *Pending Access Requests* ({len(pending_users)})\n\n"

        for user in pending_users[:20]:  # Limit to 20
            text += (
                f"• {user.full_name}\n"
                f"  @{user.username or 'N/A'} | ID: `{user.telegram_id}`\n"
                f"  Requested: {user.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            )

        if len(pending_users) > 20:
            text += f"... and {len(pending_users) - 20} more\n"

        text += "\nUse /approve <id> or /reject <id> to process"

        await reply_markdown(update.message, text)


@admin_required
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command - show system statistics."""
    if not update.message:
        return

    async with get_session() as session:
        repo = UserRepository(session)

        pending_count = await repo.count_by_status(UserStatus.PENDING.value)
        approved_count = await repo.count_by_status(UserStatus.APPROVED.value)
        suspended_count = await repo.count_by_status(UserStatus.SUSPENDED.value)
        banned_count = await repo.count_by_status(UserStatus.BANNED.value)

        total = pending_count + approved_count + suspended_count + banned_count

        logger.info(
            "Command received",
            update_type="command",
            command="/stats",
            telegram_id=update.effective_user.id if update.effective_user else None,
        )

        text = f"""
📊 *System Statistics*

*Users:*
• Total: {total}
• Approved: {approved_count}
• Pending: {pending_count}
• Suspended: {suspended_count}
• Banned: {banned_count}

*System:*
• Environment: {settings.environment}
• Debug: {"On" if settings.debug else "Off"}
• Rate Limit: {settings.rate_limit_messages_per_minute}/min
"""

        await reply_markdown(update.message, text)


# Create handlers
approve_handler = CommandHandler("approve", approve_command)
reject_handler = CommandHandler("reject", reject_command)
pending_handler = CommandHandler("pending", pending_command)
stats_handler = CommandHandler("stats", stats_command)
