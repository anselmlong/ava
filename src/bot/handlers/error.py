"""Error handler for the Telegram bot."""

import traceback
from telegram import Update
from telegram.ext import ContextTypes

from src.config.logging import get_logger

logger = get_logger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors that occur during bot operation."""
    logger.error(
        "Exception while handling an update",
        error=str(context.error),
        traceback=traceback.format_exception(
            type(context.error),
            context.error,
            context.error.__traceback__ if context.error else None,
        ),
    )

    # Try to notify the user
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "An error occurred while processing your request. "
                "Please try again later."
            )
        except Exception as e:
            logger.error("Failed to send error message to user", error=str(e))
