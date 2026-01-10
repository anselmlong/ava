"""SQLAlchemy database models."""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    type_annotation_map = {
        dict: JSONB,
        list: JSONB,
    }


class UserStatus(str, Enum):
    """User account status."""

    PENDING = "pending"
    APPROVED = "approved"
    SUSPENDED = "suspended"
    BANNED = "banned"


class MessageRole(str, Enum):
    """Message role in conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class AccessRequestStatus(str, Enum):
    """Access request status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MemoryType(str, Enum):
    """Memory type classification."""

    FACT = "fact"  # User-stated facts ("I live in San Francisco")
    PREFERENCE = "preference"  # User preferences ("I prefer morning workouts")
    CONVERSATION = "conversation"  # Important conversation excerpts
    ENTITY = "entity"  # People, places, events mentioned
    WORKFLOW = "workflow"  # Learned patterns ("User always checks email at 9 AM")


class User(Base):
    """User model representing Telegram users."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))
    language_code: Mapped[Optional[str]] = mapped_column(String(10))
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")

    # Access control
    status: Mapped[str] = mapped_column(
        String(20), default=UserStatus.PENDING.value, index=True
    )
    approved_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Preferences
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Retention settings
    conversation_retention_days: Mapped[int] = mapped_column(Integer, default=180)
    auto_archive_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Usage tracking
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_active: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )
    approved_users: Mapped[List["User"]] = relationship(
        "User", back_populates="approver", foreign_keys=[approved_by]
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="approved_users",
        remote_side=[id],
        foreign_keys=[approved_by],
    )

    @property
    def is_approved(self) -> bool:
        """Check if user is approved."""
        return self.status == UserStatus.APPROVED.value

    @property
    def is_pending(self) -> bool:
        """Check if user is pending approval."""
        return self.status == UserStatus.PENDING.value

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or self.username or str(self.telegram_id)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, status={self.status})>"


class Conversation(Base):
    """Conversation model for tracking chat sessions."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    telegram_chat_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(255))
    context: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Status
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    @property
    def is_active(self) -> bool:
        """Check if conversation is active."""
        return self.ended_at is None and not self.archived

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, user_id={self.user_id})>"


# Index for active conversations
Index(
    "idx_conversations_active",
    Conversation.user_id,
    Conversation.ended_at,
    postgresql_where=(Conversation.ended_at.is_(None)),
)


class Message(Base):
    """Message model for storing conversation messages."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_message_id: Mapped[Optional[int]] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role})>"


class AccessRequest(Base):
    """Access request model for user approval workflow."""

    __tablename__ = "access_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Request details
    reason: Mapped[Optional[str]] = mapped_column(Text)
    referral_code: Mapped[Optional[str]] = mapped_column(String(50))

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default=AccessRequestStatus.PENDING.value, index=True
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    reviewer: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[reviewed_by]
    )

    @property
    def is_pending(self) -> bool:
        """Check if request is pending."""
        return self.status == AccessRequestStatus.PENDING.value

    @property
    def full_name(self) -> str:
        """Get requester's full name."""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or self.username or str(self.telegram_id)

    def __repr__(self) -> str:
        return f"<AccessRequest(id={self.id}, telegram_id={self.telegram_id}, status={self.status})>"


class MemoryEmbedding(Base):
    """Memory embedding model for semantic long-term memory using pgvector."""

    __tablename__ = "memory_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Memory content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    # Note: embedding column is added via migration with pgvector VECTOR(768) type

    # Memory categorization
    memory_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=MemoryType.FACT.value, index=True
    )
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))

    # Context
    source_conversation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="SET NULL")
    )
    source_message_ids: Mapped[Optional[List[int]]] = mapped_column(
        ARRAY(Integer), default=list
    )

    # Importance and retrieval
    importance_score: Mapped[float] = mapped_column(Float, default=0.5)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Metadata
    memory_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String(100)), default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    source_conversation: Mapped[Optional["Conversation"]] = relationship(
        "Conversation", foreign_keys=[source_conversation_id]
    )

    @property
    def is_deleted(self) -> bool:
        """Check if memory is soft deleted."""
        return self.deleted_at is not None

    def __repr__(self) -> str:
        return f"<MemoryEmbedding(id={self.id}, user_id={self.user_id}, type={self.memory_type})>"


# Indexes for memory_embeddings (HNSW index added via migration)
Index(
    "idx_memory_importance",
    MemoryEmbedding.importance_score.desc(),
)
Index(
    "idx_memory_active",
    MemoryEmbedding.user_id,
    MemoryEmbedding.deleted_at,
    postgresql_where=(MemoryEmbedding.deleted_at.is_(None)),
)


class MemoryConsolidation(Base):
    """Tracks memory consolidation operations."""

    __tablename__ = "memory_consolidations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Consolidation details
    source_memory_ids: Mapped[List[int]] = mapped_column(ARRAY(Integer), nullable=False)
    consolidated_memory_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("memory_embeddings.id", ondelete="SET NULL")
    )
    consolidation_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    consolidated_memory: Mapped[Optional["MemoryEmbedding"]] = relationship(
        "MemoryEmbedding", foreign_keys=[consolidated_memory_id]
    )

    def __repr__(self) -> str:
        return f"<MemoryConsolidation(id={self.id}, user_id={self.user_id})>"
