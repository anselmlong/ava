"""Error handler for the Telegram bot."""

import traceback
from typing import cast

from telegram import Update
from telegram.ext import ContextTypes

from src.config.logging import get_logger
from src.bot.markdown import reply_markdown

logger = get_logger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors that occur during bot operation."""
    err = cast(BaseException | None, context.error)

    formatted_traceback = traceback.format_exception(err) if err else []

    logger.error(
        "Exception while handling an update",
        error=str(err),
        traceback=formatted_traceback,
    )

    # Try to notify the user
    if isinstance(update, Update) and update.effective_message:
        try:
            await reply_markdown(
                update.effective_message,
                "An error occurred while processing your request. "
                "Please try again later.",
            )
        except Exception as e:
            logger.error("Failed to send error message to user", error=str(e))
