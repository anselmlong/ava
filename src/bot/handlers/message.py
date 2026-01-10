"""Message handler for processing user messages."""

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.constants import ChatAction

from src.config.settings import settings
from src.config.logging import get_logger
from src.db import get_session
from src.db.repositories.user import UserRepository
from src.db.repositories.conversation import ConversationRepository
from src.db.models import UserStatus
from src.services.llm.gemini import get_gemini_service

logger = get_logger(__name__)


TELEGRAM_SAFE_MESSAGE_LENGTH = 3900


def _split_text_for_telegram(
    text: str, max_len: int = TELEGRAM_SAFE_MESSAGE_LENGTH
) -> list[str]:
    """Split text into chunks that fit Telegram message limits."""
    if not text:
        return [""]

    if max_len <= 0:
        return [text]

    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    current = ""

    for paragraph in text.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}" if current else paragraph

        if len(candidate) <= max_len:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= max_len:
            current = paragraph
            continue

        # Paragraph itself is too long; hard-split.
        for i in range(0, len(paragraph), max_len):
            chunks.append(paragraph[i : i + max_len])

    if current:
        chunks.append(current)

    return chunks


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    if not update.effective_user or not update.message or not update.message.text:
        return

    telegram_user = update.effective_user
    message_text = update.message.text
    chat_id = update.effective_chat.id if update.effective_chat else telegram_user.id

    logger.info(
        "Message received",
        telegram_id=telegram_user.id,
        message_length=len(message_text),
    )

    async with get_session() as session:
        user_repo = UserRepository(session)
        conv_repo = ConversationRepository(session)

        # Get or create user
        user = await user_repo.get_by_telegram_id(telegram_user.id)

        if not user:
            # User not registered, prompt to /start
            await update.message.reply_text(
                "Please use /start to register before sending messages."
            )
            return

        # Check user status
        if user.status == UserStatus.PENDING.value:
            await update.message.reply_text(
                "Your access request is still pending approval. "
                "Please wait for an administrator to review it."
            )
            return
        elif user.status == UserStatus.SUSPENDED.value:
            await update.message.reply_text(
                "Your account has been suspended. Please contact an administrator."
            )
            return
        elif user.status == UserStatus.BANNED.value:
            # Silently ignore banned users
            return

        # User is approved, process message
        try:
            # Show typing indicator
            await context.bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING,
            )

            # Get or create conversation
            conversation, _ = await conv_repo.get_or_create_active(
                user_id=user.id,
                telegram_chat_id=chat_id,
            )

            # Add user message to conversation
            await conv_repo.add_user_message(
                conversation_id=conversation.id,
                content=message_text,
                telegram_message_id=update.message.message_id,
            )

            # Update user activity
            await user_repo.update_activity(user.id)

            # Get conversation history for context
            history = await conv_repo.get_message_history_for_llm(
                conversation_id=conversation.id,
                limit=10,
            )
            # Remove the last message (current one) from history
            history = history[:-1] if history else []

            # Generate response using Gemini
            gemini = get_gemini_service()
            response_text = await gemini.generate(
                message=message_text,
                history=history,
            )

            # Send response (chunked to avoid Telegram "Message is too long")
            chunks = _split_text_for_telegram(response_text)
            total_chunks = len(chunks)

            for idx, chunk in enumerate(chunks):
                if idx == 0:
                    sent_message = await update.message.reply_text(chunk)
                else:
                    sent_message = await context.bot.send_message(
                        chat_id=chat_id,
                        text=chunk,
                    )

                # Save assistant response chunk
                await conv_repo.add_message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=chunk,
                    telegram_message_id=sent_message.message_id,
                    metadata={
                        "chunk_index": idx + 1,
                        "chunk_total": total_chunks,
                    },
                )

            logger.info(
                "Response sent",
                telegram_id=telegram_user.id,
                response_length=len(response_text),
            )

        except Exception as e:
            logger.error(
                "Error processing message",
                telegram_id=telegram_user.id,
                error=str(e),
            )
            await update.message.reply_text(
                "I'm sorry, I encountered an error processing your message. "
                "Please try again."
            )


# Create handler
message_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    handle_message,
)
