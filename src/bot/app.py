"""Main Telegram bot application."""

from telegram.ext import Application, ContextTypes

from src.services.reminder_delivery import deliver_due_reminders

from src.config.settings import settings
from src.config.logging import get_logger, setup_logging
from src.db import init_db, close_db, get_session
from src.bot.handlers import (
    start_handler,
    help_handler,
    settings_handler,
    goal_handler,
    goals_handler,
    remind_handler,
    reminders_handler,
    message_handler,
    approve_handler,
    reject_handler,
    pending_handler,
    stats_handler,
    error_handler,
)

logger = get_logger(__name__)


async def _reminder_dispatch_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    async with get_session() as session:
        delivered = await deliver_due_reminders(
            session=session,
            send_message=lambda chat_id, text: context.bot.send_message(
                chat_id=chat_id, text=text
            ),
            batch_size=settings.reminder_dispatch_batch_size,
        )

    if delivered:
        logger.info("Delivered reminders", count=delivered)


async def post_init(application: Application) -> None:
    """Initialize resources after the bot starts."""
    logger.info("Initializing database connection...")
    await init_db()
    logger.info("Database initialized")

    if application.job_queue:
        application.job_queue.run_repeating(
            _reminder_dispatch_job,
            interval=settings.reminder_poll_interval_seconds,
            first=5,
            name="reminder-dispatch",
        )
        logger.info(
            "Scheduled reminder dispatcher",
            interval_seconds=settings.reminder_poll_interval_seconds,
        )
    else:
        logger.warning("JobQueue not available; reminders will not be dispatched")


async def post_shutdown(application: Application) -> None:
    """Clean up resources after the bot shuts down."""
    logger.info("Closing database connection...")
    await close_db()
    logger.info("Database connection closed")


def create_bot() -> Application:
    """Create and configure the Telegram bot application."""
    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    # Build application
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Register command handlers
    application.add_handler(start_handler)
    application.add_handler(help_handler)
    application.add_handler(settings_handler)
    application.add_handler(goal_handler)
    application.add_handler(goals_handler)
    application.add_handler(remind_handler)
    application.add_handler(reminders_handler)

    # Register admin handlers
    application.add_handler(approve_handler)
    application.add_handler(reject_handler)
    application.add_handler(pending_handler)
    application.add_handler(stats_handler)

    # Register message handler (should be last)
    application.add_handler(message_handler)

    # Register error handler
    application.add_error_handler(error_handler)

    return application


def run_bot() -> None:
    """Run the bot."""
    setup_logging()

    logger.info(
        "Starting Ava bot",
        environment=settings.environment,
        debug=settings.debug,
    )

    application = create_bot()

    # Run the bot
    application.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )
