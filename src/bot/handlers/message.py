"""Message handler for processing user messages."""

from datetime import datetime, timezone, timedelta

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.constants import ChatAction

from src.config.settings import settings
from src.config.logging import get_logger
from src.bot.markdown import reply_markdown, send_markdown
from src.db import get_session
from src.db.repositories.user import UserRepository
from src.db.repositories.conversation import ConversationRepository
from src.db.models import UserStatus, MessageRole
from src.services.llm.gemini import get_gemini_service
from src.services.mem0_service import get_mem0_service

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


def _truncate_for_memory(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None

    try:
        normalized = value
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    if not update.effective_user or not update.message or not update.message.text:
        return

    telegram_user = update.effective_user
    message_text = update.message.text
    chat_id = update.effective_chat.id if update.effective_chat else telegram_user.id

    logger.info(
        "Message received",
        update_type="message",
        telegram_id=telegram_user.id,
        message_length=len(message_text),
        ava_route="langgraph" if settings.langgraph_agent_enabled else "direct",
    )

    async with get_session() as session:
        user_repo = UserRepository(session)
        conv_repo = ConversationRepository(session)

        # Get or create user
        user = await user_repo.get_by_telegram_id(telegram_user.id)

        if not user:
            # User not registered, prompt to /start
            await reply_markdown(
                update.message,
                "Please use /start to register before sending messages.",
            )
            return

        # Check user status
        if user.status == UserStatus.PENDING.value:
            await reply_markdown(
                update.message,
                "Your access request is still pending approval. "
                "Please wait for an administrator to review it.",
            )
            return
        elif user.status == UserStatus.SUSPENDED.value:
            await reply_markdown(
                update.message,
                "Your account has been suspended. Please contact an administrator.",
            )
            return
        elif user.status == UserStatus.BANNED.value:
            # Silently ignore banned users
            return

        # User is approved, process message
        try:
            now = datetime.now(timezone.utc)

            # Rate limiting (per user)
            if settings.rate_limit_enabled:
                window_start = now - timedelta(minutes=1)
                recent_count = await conv_repo.count_user_messages_since(
                    user_id=user.id,
                    since=window_start,
                )
                if recent_count >= settings.rate_limit_messages_per_minute:
                    await reply_markdown(
                        update.message,
                        "You're sending messages too quickly. Please wait a moment and try again.",
                    )
                    return

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
            history_since = None
            if user.conversation_retention_days > 0:
                history_since = now - timedelta(days=user.conversation_retention_days)

            history = await conv_repo.get_message_history_for_llm(
                conversation_id=conversation.id,
                limit=10,
                since=history_since,
            )
            # Remove the last message (current one) from history
            history = history[:-1] if history else []

            memory_enabled_for_user = user.conversation_retention_days > 0

            response_text: str
            decision_trace: list[str] = []

            if settings.langgraph_agent_enabled:
                # Lazy import so the bot can still start without LangGraph installed.
                from src.agent import run_agent_turn

                decision_trace.append("route:langgraph")
                response_text = await run_agent_turn(
                    session=session,
                    user_id=user.id,
                    conversation_id=conversation.id,
                    message_text=message_text,
                    history=history,
                    memory_enabled=memory_enabled_for_user,
                )
            else:
                decision_trace.append("route:direct")
                # Optional long-term memory retrieval via Mem0
                memory_context = ""
                if settings.memory_read_enabled and memory_enabled_for_user:
                    try:
                        mem0 = get_mem0_service()
                        memory_context = mem0.get_context(
                            user_id=user.id,
                            query=message_text,
                            limit=settings.memory_retrieval_top_k,
                        )
                        decision_trace.append(
                            "memory:used" if memory_context else "memory:none"
                        )
                    except Exception as e:
                        logger.warning(
                            "Memory retrieval failed",
                            telegram_id=telegram_user.id,
                            error=str(e),
                        )
                        decision_trace.append("memory:error")
                        memory_context = ""

                # Generate response using Gemini
                gemini = get_gemini_service()
                system_prompt = None
                if memory_context:
                    system_prompt = (
                        gemini.system_prompt
                        + "\n\n"
                        + memory_context
                        + "\n\nUse the relevant memories only if they help answer the user. If they seem unrelated, ignore them."
                    )

                response_text = await gemini.generate(
                    message=message_text,
                    history=history,
                    system_prompt=system_prompt,
                )
                decision_trace.append("llm:generated")

            # Send response (chunked to avoid Telegram "Message is too long")
            chunks = _split_text_for_telegram(response_text)
            total_chunks = len(chunks)

            for idx, chunk in enumerate(chunks):
                if idx == 0:
                    sent_message = await reply_markdown(update.message, chunk)
                else:
                    sent_message = await send_markdown(
                        context.bot,
                        chat_id=chat_id,
                        text=chunk,
                    )

                # Save assistant response chunk
                await conv_repo.add_message(
                    conversation_id=conversation.id,
                    role=MessageRole.ASSISTANT.value,
                    content=chunk,
                    telegram_message_id=sent_message.message_id,
                    metadata={
                        "chunk_index": idx + 1,
                        "chunk_total": total_chunks,
                    },
                )

            # Optional long-term memory writing via Mem0
            if (
                (not settings.langgraph_agent_enabled)
                and settings.memory_write_enabled
                and memory_enabled_for_user
            ):
                try:
                    mem0 = get_mem0_service()
                    messages = [
                        {"role": "user", "content": _truncate_for_memory(message_text, 1500)},
                        {"role": "assistant", "content": _truncate_for_memory(response_text, 1500)},
                    ]
                    mem0.store_conversation(user_id=user.id, messages=messages)
                except Exception as e:
                    logger.warning(
                        "Memory write failed",
                        telegram_id=telegram_user.id,
                        error=str(e),
                    )

            logger.info(
                "Response sent",
                telegram_id=telegram_user.id,
                ava_route="langgraph" if settings.langgraph_agent_enabled else "direct",
                ava_decision_trace=decision_trace,
                response_length=len(response_text),
            )

        except Exception as e:
            logger.error(
                "Error processing message",
                telegram_id=telegram_user.id,
                error=str(e),
            )
            await reply_markdown(
                update.message,
                "I'm sorry, I encountered an error processing your message. "
                "Please try again.",
            )


# Create handler
message_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    handle_message,
)
