"""Memory repository for database operations with pgvector."""

from datetime import datetime, timezone
from typing import Optional, List, Tuple

from sqlalchemy import select, update, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import MemoryEmbedding, MemoryConsolidation, MemoryType
from src.config.settings import settings


class MemoryRepository:
    """Repository for Memory-related database operations using pgvector."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        content: str,
        embedding: List[float],
        memory_type: str = MemoryType.FACT.value,
        summary: Optional[str] = None,
        entity_type: Optional[str] = None,
        source_conversation_id: Optional[int] = None,
        source_message_ids: Optional[List[int]] = None,
        importance_score: float = 0.5,
        tags: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
    ) -> MemoryEmbedding:
        """Create a new memory embedding.

        Args:
            user_id: The user's database ID
            content: The memory content text
            embedding: The 768-dimensional embedding vector
            memory_type: Type of memory (fact, preference, conversation, entity, workflow)
            summary: Optional condensed version of the content
            entity_type: Optional entity classification (person, place, event, etc.)
            source_conversation_id: Optional conversation this memory came from
            source_message_ids: Optional list of message IDs this memory references
            importance_score: Importance score 0.0 to 1.0
            tags: Optional list of tags
            metadata: Optional additional metadata

        Returns:
            The created MemoryEmbedding
        """
        memory = MemoryEmbedding(
            user_id=user_id,
            content=content,
            summary=summary,
            memory_type=memory_type,
            entity_type=entity_type,
            source_conversation_id=source_conversation_id,
            source_message_ids=source_message_ids or [],
            importance_score=importance_score,
            tags=tags or [],
            memory_metadata=metadata or {},
        )
        self.session.add(memory)
        await self.session.flush()

        # Set the embedding vector using raw SQL (pgvector)
        await self.session.execute(
            text("UPDATE memory_embeddings SET embedding = :embedding WHERE id = :id"),
            {"embedding": str(embedding), "id": memory.id},
        )

        return memory

    async def get_by_id(self, memory_id: int) -> Optional[MemoryEmbedding]:
        """Get a memory by ID."""
        result = await self.session.execute(
            select(MemoryEmbedding).where(MemoryEmbedding.id == memory_id)
        )
        return result.scalar_one_or_none()

    async def search_similar(
        self,
        user_id: int,
        query_embedding: List[float],
        limit: int = 5,
        similarity_threshold: float = 0.7,
        memory_types: Optional[List[str]] = None,
    ) -> List[Tuple[MemoryEmbedding, float]]:
        """Search for similar memories using cosine similarity.

        Args:
            user_id: The user's database ID
            query_embedding: The query embedding vector
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score (0-1)
            memory_types: Optional filter by memory types

        Returns:
            List of tuples containing (MemoryEmbedding, similarity_score)
        """
        # Convert embedding to string format for pgvector.
        # Keep it parameterized to avoid logging or interpolating huge vectors.
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Build the query with cosine similarity.
        # 1 - cosine_distance gives us cosine similarity (0 to 1).
        # Use CAST(:embedding AS vector) to avoid the ::vector syntax ambiguity in SQLAlchemy text().
        if memory_types:
            query = text(
                """
                SELECT
                    m.id,
                    m.user_id,
                    m.content,
                    m.summary,
                    m.memory_type,
                    m.entity_type,
                    m.source_conversation_id,
                    m.source_message_ids,
                    m.importance_score,
                    m.access_count,
                    m.last_accessed,
                    m.memory_metadata,
                    m.tags,
                    m.created_at,
                    m.updated_at,
                    m.deleted_at,
                    1 - (m.embedding <=> CAST(:embedding AS vector)) as similarity
                FROM memory_embeddings m
                WHERE m.user_id = :user_id
                  AND m.deleted_at IS NULL
                  AND m.embedding IS NOT NULL
                  AND 1 - (m.embedding <=> CAST(:embedding AS vector)) >= :threshold
                  AND m.memory_type = ANY(:memory_types)
                ORDER BY similarity DESC
                LIMIT :limit
                """
            )
            params = {
                "user_id": user_id,
                "embedding": embedding_str,
                "threshold": similarity_threshold,
                "limit": limit,
                "memory_types": memory_types,
            }
        else:
            query = text(
                """
                SELECT
                    m.id,
                    m.user_id,
                    m.content,
                    m.summary,
                    m.memory_type,
                    m.entity_type,
                    m.source_conversation_id,
                    m.source_message_ids,
                    m.importance_score,
                    m.access_count,
                    m.last_accessed,
                    m.memory_metadata,
                    m.tags,
                    m.created_at,
                    m.updated_at,
                    m.deleted_at,
                    1 - (m.embedding <=> CAST(:embedding AS vector)) as similarity
                FROM memory_embeddings m
                WHERE m.user_id = :user_id
                  AND m.deleted_at IS NULL
                  AND m.embedding IS NOT NULL
                  AND 1 - (m.embedding <=> CAST(:embedding AS vector)) >= :threshold
                ORDER BY similarity DESC
                LIMIT :limit
                """
            )
            params = {
                "user_id": user_id,
                "embedding": embedding_str,
                "threshold": similarity_threshold,
                "limit": limit,
            }

        result = await self.session.execute(query, params)
        rows = result.fetchall()

        # Convert rows to MemoryEmbedding objects with similarity scores
        memories_with_scores = []
        for row in rows:
            memory = MemoryEmbedding(
                id=row.id,
                user_id=row.user_id,
                content=row.content,
                summary=row.summary,
                memory_type=row.memory_type,
                entity_type=row.entity_type,
                source_conversation_id=row.source_conversation_id,
                source_message_ids=row.source_message_ids,
                importance_score=row.importance_score,
                access_count=row.access_count,
                last_accessed=row.last_accessed,
                memory_metadata=row.memory_metadata,
                tags=row.tags,
                created_at=row.created_at,
                updated_at=row.updated_at,
                deleted_at=row.deleted_at,
            )
            memories_with_scores.append((memory, row.similarity))

        return memories_with_scores

    async def get_user_memories(
        self,
        user_id: int,
        memory_type: Optional[str] = None,
        limit: int = 50,
        include_deleted: bool = False,
    ) -> List[MemoryEmbedding]:
        """Get all memories for a user.

        Args:
            user_id: The user's database ID
            memory_type: Optional filter by memory type
            limit: Maximum number of results
            include_deleted: Whether to include soft-deleted memories

        Returns:
            List of MemoryEmbedding objects
        """
        query = select(MemoryEmbedding).where(MemoryEmbedding.user_id == user_id)

        if not include_deleted:
            query = query.where(MemoryEmbedding.deleted_at.is_(None))

        if memory_type:
            query = query.where(MemoryEmbedding.memory_type == memory_type)

        query = query.order_by(MemoryEmbedding.created_at.desc()).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_access(self, memory_id: int) -> None:
        """Update memory access count and timestamp."""
        await self.session.execute(
            update(MemoryEmbedding)
            .where(MemoryEmbedding.id == memory_id)
            .values(
                access_count=MemoryEmbedding.access_count + 1,
                last_accessed=datetime.now(timezone.utc),
            )
        )

    async def update_importance(
        self, memory_id: int, importance_score: float
    ) -> Optional[MemoryEmbedding]:
        """Update memory importance score."""
        memory = await self.get_by_id(memory_id)
        if not memory:
            return None

        memory.importance_score = max(0.0, min(1.0, importance_score))
        memory.updated_at = datetime.now(timezone.utc)
        return memory

    async def soft_delete(self, memory_id: int) -> Optional[MemoryEmbedding]:
        """Soft delete a memory."""
        memory = await self.get_by_id(memory_id)
        if not memory:
            return None

        memory.deleted_at = datetime.now(timezone.utc)
        return memory

    async def hard_delete(self, memory_id: int) -> bool:
        """Permanently delete a memory."""
        memory = await self.get_by_id(memory_id)
        if not memory:
            return False

        await self.session.delete(memory)
        return True

    async def find_similar_for_consolidation(
        self,
        user_id: int,
        similarity_threshold: float = 0.9,
        limit: int = 100,
    ) -> List[Tuple[MemoryEmbedding, MemoryEmbedding, float]]:
        """Find pairs of similar memories that could be consolidated.

        Args:
            user_id: The user's database ID
            similarity_threshold: Minimum similarity for consolidation candidates
            limit: Maximum number of pairs to return

        Returns:
            List of tuples (memory1, memory2, similarity)
        """
        # Find pairs of memories with high similarity
        query = text("""
            SELECT 
                m1.id as id1,
                m2.id as id2,
                1 - (m1.embedding <=> m2.embedding) as similarity
            FROM memory_embeddings m1
            JOIN memory_embeddings m2 ON m1.id < m2.id
            WHERE m1.user_id = :uid
              AND m2.user_id = :uid
              AND m1.deleted_at IS NULL
              AND m2.deleted_at IS NULL
              AND m1.embedding IS NOT NULL
              AND m2.embedding IS NOT NULL
              AND 1 - (m1.embedding <=> m2.embedding) >= :thresh
            ORDER BY similarity DESC
            LIMIT :lim
        """)

        result = await self.session.execute(
            query,
            {
                "uid": user_id,
                "thresh": similarity_threshold,
                "lim": limit,
            },
        )
        rows = result.fetchall()

        # Fetch the actual memory objects
        pairs = []
        for row in rows:
            m1 = await self.get_by_id(row.id1)
            m2 = await self.get_by_id(row.id2)
            if m1 and m2:
                pairs.append((m1, m2, row.similarity))

        return pairs

    async def create_consolidation(
        self,
        user_id: int,
        source_memory_ids: List[int],
        consolidated_memory_id: int,
        reason: Optional[str] = None,
    ) -> MemoryConsolidation:
        """Create a consolidation record.

        Args:
            user_id: The user's database ID
            source_memory_ids: IDs of memories that were consolidated
            consolidated_memory_id: ID of the new consolidated memory
            reason: Optional reason for consolidation

        Returns:
            The created MemoryConsolidation
        """
        consolidation = MemoryConsolidation(
            user_id=user_id,
            source_memory_ids=source_memory_ids,
            consolidated_memory_id=consolidated_memory_id,
            consolidation_reason=reason,
        )
        self.session.add(consolidation)
        await self.session.flush()
        return consolidation

    async def count_user_memories(
        self,
        user_id: int,
        include_deleted: bool = False,
    ) -> int:
        """Count total memories for a user."""
        query = select(func.count(MemoryEmbedding.id)).where(
            MemoryEmbedding.user_id == user_id
        )

        if not include_deleted:
            query = query.where(MemoryEmbedding.deleted_at.is_(None))

        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_memories_by_conversation(
        self,
        conversation_id: int,
    ) -> List[MemoryEmbedding]:
        """Get all memories derived from a specific conversation."""
        result = await self.session.execute(
            select(MemoryEmbedding)
            .where(
                MemoryEmbedding.source_conversation_id == conversation_id,
                MemoryEmbedding.deleted_at.is_(None),
            )
            .order_by(MemoryEmbedding.created_at)
        )
        return list(result.scalars().all())
