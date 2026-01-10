"""Telegram Markdown helpers.

We prefer sending Markdown so Ava responses render nicely, but Telegram will
reject malformed Markdown. These helpers fall back to plain text if parsing
fails.
"""

from __future__ import annotations

from telegram import Bot, Message
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.helpers import escape_markdown

from src.config.logging import get_logger

logger = get_logger(__name__)


async def reply_markdown(
    message: Message,
    text: str,
    *,
    disable_web_page_preview: bool = True,
) -> Message:
    try:
        return await message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=disable_web_page_preview,
        )
    except BadRequest as exc:
        logger.warning(
            "Telegram Markdown rejected message",
            error=str(exc),
            text_length=len(text),
        )

        # Try escaping and sending again with Markdown (preserves parse_mode).
        safe_text = escape_markdown(text, version=1)
        try:
            return await message.reply_text(
                safe_text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=disable_web_page_preview,
            )
        except BadRequest:
            # Last resort: plain text.
            return await message.reply_text(
                text,
                disable_web_page_preview=disable_web_page_preview,
            )


async def send_markdown(
    bot: Bot,
    *,
    chat_id: int,
    text: str,
    disable_web_page_preview: bool = True,
) -> Message:
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=disable_web_page_preview,
        )
    except BadRequest as exc:
        logger.warning(
            "Telegram Markdown rejected message",
            error=str(exc),
            text_length=len(text),
        )

        safe_text = escape_markdown(text, version=1)
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=safe_text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=disable_web_page_preview,
            )
        except BadRequest:
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                disable_web_page_preview=disable_web_page_preview,
            )
