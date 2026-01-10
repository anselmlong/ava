"""Conversation repository for database operations."""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Conversation, Message, MessageRole


class ConversationRepository:
    """Repository for Conversation-related database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        conversation_id: int,
        include_messages: bool = False,
    ) -> Optional[Conversation]:
        """Get conversation by ID."""
        query = select(Conversation).where(Conversation.id == conversation_id)
        if include_messages:
            query = query.options(selectinload(Conversation.messages))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_for_user(
        self,
        user_id: int,
        telegram_chat_id: int,
    ) -> Optional[Conversation]:
        """Get the active conversation for a user in a specific chat."""
        result = await self.session.execute(
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.telegram_chat_id == telegram_chat_id,
                Conversation.ended_at.is_(None),
                Conversation.archived == False,
            )
            .order_by(Conversation.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        telegram_chat_id: int,
        title: Optional[str] = None,
    ) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(
            user_id=user_id,
            telegram_chat_id=telegram_chat_id,
            title=title,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get_or_create_active(
        self,
        user_id: int,
        telegram_chat_id: int,
    ) -> tuple[Conversation, bool]:
        """Get or create an active conversation.

        Returns:
            Tuple of (conversation, created) where created is True if newly created
        """
        conversation = await self.get_active_for_user(user_id, telegram_chat_id)
        if conversation:
            return conversation, False

        conversation = await self.create(user_id, telegram_chat_id)
        return conversation, True

    async def end_conversation(self, conversation_id: int) -> Optional[Conversation]:
        """End a conversation."""
        conversation = await self.get_by_id(conversation_id)
        if not conversation:
            return None

        conversation.ended_at = datetime.now(timezone.utc)
        return conversation

    async def archive_conversation(
        self, conversation_id: int
    ) -> Optional[Conversation]:
        """Archive a conversation."""
        conversation = await self.get_by_id(conversation_id)
        if not conversation:
            return None

        conversation.archived = True
        if not conversation.ended_at:
            conversation.ended_at = datetime.now(timezone.utc)
        return conversation

    async def get_recent_messages(
        self,
        conversation_id: int,
        limit: int = 10,
    ) -> List[Message]:
        """Get recent messages from a conversation."""
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        # Return in chronological order
        return list(reversed(messages))

    async def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        telegram_message_id: Optional[int] = None,
        metadata: Optional[dict] = None,
        token_count: Optional[int] = None,
    ) -> Message:
        """Add a message to a conversation."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            telegram_message_id=telegram_message_id,
            message_metadata=metadata or {},
            token_count=token_count,
        )
        self.session.add(message)

        # Update conversation message count
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(message_count=Conversation.message_count + 1)
        )

        await self.session.flush()
        return message

    async def add_user_message(
        self,
        conversation_id: int,
        content: str,
        telegram_message_id: Optional[int] = None,
    ) -> Message:
        """Add a user message to a conversation."""
        return await self.add_message(
            conversation_id=conversation_id,
            role=MessageRole.USER.value,
            content=content,
            telegram_message_id=telegram_message_id,
        )

    async def add_assistant_message(
        self,
        conversation_id: int,
        content: str,
        telegram_message_id: Optional[int] = None,
        token_count: Optional[int] = None,
    ) -> Message:
        """Add an assistant message to a conversation."""
        return await self.add_message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT.value,
            content=content,
            telegram_message_id=telegram_message_id,
            token_count=token_count,
        )

    async def get_user_conversations(
        self,
        user_id: int,
        include_archived: bool = False,
        limit: int = 20,
    ) -> List[Conversation]:
        """Get conversations for a user."""
        query = select(Conversation).where(Conversation.user_id == user_id)

        if not include_archived:
            query = query.where(Conversation.archived == False)

        query = query.order_by(Conversation.started_at.desc()).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_message_history_for_llm(
        self,
        conversation_id: int,
        limit: int = 10,
    ) -> List[dict]:
        """Get message history formatted for LLM context.

        Returns list of dicts with 'role' and 'content' keys.
        """
        messages = await self.get_recent_messages(conversation_id, limit)
        return [{"role": msg.role, "content": msg.content} for msg in messages]
