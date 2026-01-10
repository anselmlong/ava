"""Memory service for semantic long-term memory management.

This service provides the high-level API for:
- Storing memories with automatic embedding generation
- Retrieving relevant memories using semantic search
- Memory consolidation to reduce redundancy
- Automatic fact extraction from conversations
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.config.logging import get_logger
from src.db.models import MemoryEmbedding, MemoryType
from src.db.repositories.memory import MemoryRepository
from src.services.embedding import get_embedding_service, EmbeddingService
from src.services.llm.gemini import get_gemini_service, GeminiService

logger = get_logger(__name__)


class MemoryService:
    """Service for managing semantic long-term memory.

    Provides storage, retrieval, and consolidation of user memories
    using pgvector for semantic similarity search.
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: Optional[EmbeddingService] = None,
        llm_service: Optional[GeminiService] = None,
    ):
        """Initialize the memory service.

        Args:
            session: Database session for repository operations
            embedding_service: Optional embedding service (uses singleton if not provided)
            llm_service: Optional LLM service for importance scoring and consolidation
        """
        self.repository = MemoryRepository(session)
        self.embedding_service = embedding_service or get_embedding_service()
        self.llm_service = llm_service or get_gemini_service()

    async def store_memory(
        self,
        user_id: int,
        content: str,
        memory_type: str = MemoryType.FACT.value,
        summary: Optional[str] = None,
        entity_type: Optional[str] = None,
        source_conversation_id: Optional[int] = None,
        source_message_ids: Optional[List[int]] = None,
        importance_score: Optional[float] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
    ) -> MemoryEmbedding:
        """Store a new memory with automatic embedding generation.

        Args:
            user_id: The user's database ID
            content: The memory content to store
            memory_type: Type of memory (fact, preference, conversation, entity, workflow)
            summary: Optional summary of the content
            entity_type: Optional entity type for entity memories
            source_conversation_id: Optional source conversation
            source_message_ids: Optional source message IDs
            importance_score: Optional importance score (auto-calculated if not provided)
            tags: Optional list of tags
            metadata: Optional additional metadata

        Returns:
            The created MemoryEmbedding
        """
        # Generate embedding
        embedding = await self.embedding_service.embed_text(content)

        # Calculate importance score if not provided
        if importance_score is None:
            importance_score = await self._calculate_importance(content, memory_type)

        # Create memory in database
        memory = await self.repository.create(
            user_id=user_id,
            content=content,
            embedding=embedding,
            memory_type=memory_type,
            summary=summary,
            entity_type=entity_type,
            source_conversation_id=source_conversation_id,
            source_message_ids=source_message_ids,
            importance_score=importance_score,
            tags=tags,
            metadata=metadata,
        )

        logger.info(
            "Stored new memory",
            memory_id=memory.id,
            user_id=user_id,
            memory_type=memory_type,
            importance=importance_score,
        )

        return memory

    async def retrieve_relevant_memories(
        self,
        user_id: int,
        query: str,
        limit: Optional[int] = None,
        memory_types: Optional[List[str]] = None,
        include_scores: bool = False,
    ) -> List[Dict[str, Any]]:
        """Retrieve memories relevant to a query using semantic search.

        The retrieval uses a weighted scoring formula:
        final_score = similarity * (1 - recency_weight - importance_weight)
                    + recency_score * recency_weight
                    + importance_score * importance_weight

        Args:
            user_id: The user's database ID
            query: The query to find relevant memories for
            limit: Maximum number of memories to retrieve (default from settings)
            memory_types: Optional filter by memory types
            include_scores: Whether to include similarity scores in results

        Returns:
            List of memory dictionaries with optional scores
        """
        limit = limit or settings.memory_retrieval_top_k

        # Generate query embedding
        query_embedding = await self.embedding_service.embed_query(query)

        # Search for similar memories
        results = await self.repository.search_similar(
            user_id=user_id,
            query_embedding=query_embedding,
            limit=limit * 2,  # Get more for re-ranking
            similarity_threshold=settings.memory_similarity_threshold,
            memory_types=memory_types,
        )

        if not results:
            return []

        # Apply weighted scoring for final ranking
        scored_memories = []
        now = datetime.now(timezone.utc)

        for memory, similarity in results:
            # Calculate recency score (exponential decay)
            age_days = (now - memory.created_at).days
            recency_score = max(0, 1 - (age_days / 365))  # Linear decay over a year

            # Calculate final score with weights
            final_score = (
                similarity
                * (
                    1
                    - settings.memory_recency_weight
                    - settings.memory_importance_weight
                )
                + recency_score * settings.memory_recency_weight
                + memory.importance_score * settings.memory_importance_weight
            )

            scored_memories.append(
                {
                    "memory": memory,
                    "similarity": similarity,
                    "recency_score": recency_score,
                    "final_score": final_score,
                }
            )

            # Update access stats
            await self.repository.update_access(memory.id)

        # Sort by final score and limit
        scored_memories.sort(key=lambda x: x["final_score"], reverse=True)
        scored_memories = scored_memories[:limit]

        # Format output
        result = []
        for item in scored_memories:
            memory = item["memory"]
            entry = {
                "id": memory.id,
                "content": memory.content,
                "summary": memory.summary,
                "memory_type": memory.memory_type,
                "entity_type": memory.entity_type,
                "importance_score": memory.importance_score,
                "tags": memory.tags,
                "created_at": memory.created_at.isoformat(),
            }
            if include_scores:
                entry["similarity"] = item["similarity"]
                entry["recency_score"] = item["recency_score"]
                entry["final_score"] = item["final_score"]
            result.append(entry)

        logger.debug(
            "Retrieved memories",
            user_id=user_id,
            query_length=len(query),
            results_count=len(result),
        )

        return result

    async def get_context_for_conversation(
        self,
        user_id: int,
        recent_messages: List[str],
        max_memories: int = 5,
    ) -> str:
        """Get relevant memory context for a conversation.

        Combines recent messages to form a query and retrieves relevant memories
        to provide context for the LLM.

        Args:
            user_id: The user's database ID
            recent_messages: List of recent message contents
            max_memories: Maximum number of memories to include

        Returns:
            Formatted string of relevant memories for LLM context
        """
        if not recent_messages:
            return ""

        # Combine recent messages for query
        query = " ".join(recent_messages[-3:])  # Use last 3 messages

        memories = await self.retrieve_relevant_memories(
            user_id=user_id,
            query=query,
            limit=max_memories,
        )

        if not memories:
            return ""

        # Format memories for LLM context
        context_parts = ["[Relevant memories from past conversations:]"]
        for mem in memories:
            mem_type = mem["memory_type"]
            content = mem["summary"] or mem["content"]
            context_parts.append(f"- [{mem_type}] {content}")

        return "\n".join(context_parts)

    async def extract_and_store_facts(
        self,
        user_id: int,
        conversation_text: str,
        conversation_id: Optional[int] = None,
    ) -> List[MemoryEmbedding]:
        """Extract facts and preferences from conversation text and store them.

        Uses the LLM to identify memorable facts, preferences, and entities
        from the conversation.

        Args:
            user_id: The user's database ID
            conversation_text: The conversation text to extract from
            conversation_id: Optional source conversation ID

        Returns:
            List of created memories
        """
        # Use LLM to extract facts
        extraction_prompt = """Analyze the following conversation and extract important facts, user preferences, and entities.
For each extracted item, provide:
1. The content (a clear statement of the fact/preference)
2. The type: "fact", "preference", "entity", or "workflow"
3. For entities, the entity_type: "person", "place", "event", "thing"
4. Importance score from 0.0 to 1.0 (how useful this info might be in future conversations)

Format each item as:
TYPE: <type>
ENTITY_TYPE: <entity_type if applicable, otherwise "none">
IMPORTANCE: <score>
CONTENT: <the fact/preference/entity description>
---

Only extract genuinely useful information. Skip trivial details.

Conversation:
"""
        try:
            response = await self.llm_service.generate(
                extraction_prompt + conversation_text,
                system_prompt="You are a fact extraction assistant. Extract only meaningful, potentially useful information.",
            )

            # Parse the response
            memories = []
            items = response.split("---")

            for item in items:
                item = item.strip()
                if not item:
                    continue

                # Parse fields
                lines = item.split("\n")
                parsed = {}
                for line in lines:
                    if ":" in line:
                        key, value = line.split(":", 1)
                        parsed[key.strip().upper()] = value.strip()

                if "CONTENT" not in parsed or "TYPE" not in parsed:
                    continue

                content = parsed["CONTENT"]
                memory_type = parsed["TYPE"].lower()
                if memory_type not in [t.value for t in MemoryType]:
                    memory_type = MemoryType.FACT.value

                entity_type = parsed.get("ENTITY_TYPE", "none")
                if entity_type.lower() == "none":
                    entity_type = None

                importance = 0.5
                try:
                    importance = float(parsed.get("IMPORTANCE", "0.5"))
                except ValueError:
                    pass

                # Store the extracted memory
                memory = await self.store_memory(
                    user_id=user_id,
                    content=content,
                    memory_type=memory_type,
                    entity_type=entity_type,
                    source_conversation_id=conversation_id,
                    importance_score=importance,
                )
                memories.append(memory)

            logger.info(
                "Extracted facts from conversation",
                user_id=user_id,
                conversation_id=conversation_id,
                extracted_count=len(memories),
            )

            return memories

        except Exception as e:
            logger.error(
                "Error extracting facts",
                error=str(e),
                user_id=user_id,
            )
            return []

    async def consolidate_similar_memories(
        self,
        user_id: int,
        similarity_threshold: Optional[float] = None,
    ) -> int:
        """Consolidate similar memories to reduce redundancy.

        Finds pairs of highly similar memories and merges them into a single
        consolidated memory.

        Args:
            user_id: The user's database ID
            similarity_threshold: Minimum similarity for consolidation

        Returns:
            Number of consolidations performed
        """
        threshold = similarity_threshold or settings.memory_consolidation_similarity

        # Find similar memory pairs
        pairs = await self.repository.find_similar_for_consolidation(
            user_id=user_id,
            similarity_threshold=threshold,
            limit=50,
        )

        if not pairs:
            return 0

        consolidations = 0
        processed_ids = set()

        for mem1, mem2, similarity in pairs:
            # Skip if either memory was already processed
            if mem1.id in processed_ids or mem2.id in processed_ids:
                continue

            # Use LLM to merge the memories
            merge_prompt = f"""Merge these two related pieces of information into a single, comprehensive statement:

1. {mem1.content}
2. {mem2.content}

Provide a single merged statement that captures all the information. Be concise but complete."""

            try:
                merged_content = await self.llm_service.generate(
                    merge_prompt,
                    system_prompt="You are a text summarization assistant. Merge information concisely.",
                )

                # Create consolidated memory
                consolidated = await self.store_memory(
                    user_id=user_id,
                    content=merged_content.strip(),
                    memory_type=mem1.memory_type,  # Use first memory's type
                    importance_score=max(mem1.importance_score, mem2.importance_score),
                    tags=list(set((mem1.tags or []) + (mem2.tags or []))),
                    metadata={"consolidated_from": [mem1.id, mem2.id]},
                )

                # Record consolidation
                await self.repository.create_consolidation(
                    user_id=user_id,
                    source_memory_ids=[mem1.id, mem2.id],
                    consolidated_memory_id=consolidated.id,
                    reason=f"Similarity: {similarity:.2f}",
                )

                # Soft delete original memories
                await self.repository.soft_delete(mem1.id)
                await self.repository.soft_delete(mem2.id)

                processed_ids.add(mem1.id)
                processed_ids.add(mem2.id)
                consolidations += 1

                logger.debug(
                    "Consolidated memories",
                    mem1_id=mem1.id,
                    mem2_id=mem2.id,
                    consolidated_id=consolidated.id,
                    similarity=similarity,
                )

            except Exception as e:
                logger.error(
                    "Error consolidating memories",
                    error=str(e),
                    mem1_id=mem1.id,
                    mem2_id=mem2.id,
                )

        logger.info(
            "Memory consolidation completed",
            user_id=user_id,
            consolidations=consolidations,
        )

        return consolidations

    async def delete_old_memories(
        self,
        user_id: int,
        retention_days: int,
    ) -> int:
        """Soft delete memories older than retention period.

        Only deletes memories with low importance scores to preserve
        critical information.

        Args:
            user_id: The user's database ID
            retention_days: Number of days to retain memories

        Returns:
            Number of memories deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        memories = await self.repository.get_user_memories(
            user_id=user_id,
            limit=1000,  # Process in batches
        )

        deleted = 0
        for memory in memories:
            # Only delete old, low-importance, infrequently accessed memories
            if (
                memory.created_at < cutoff_date
                and memory.importance_score < 0.3
                and memory.access_count < 5
            ):
                await self.repository.soft_delete(memory.id)
                deleted += 1

        logger.info(
            "Deleted old memories",
            user_id=user_id,
            retention_days=retention_days,
            deleted_count=deleted,
        )

        return deleted

    async def _calculate_importance(
        self,
        content: str,
        memory_type: str,
    ) -> float:
        """Calculate importance score for a memory.

        Args:
            content: The memory content
            memory_type: The type of memory

        Returns:
            Importance score between 0.0 and 1.0
        """
        # Base importance by type
        type_importance = {
            MemoryType.PREFERENCE.value: 0.7,  # Preferences are usually important
            MemoryType.FACT.value: 0.5,  # Facts have medium importance
            MemoryType.ENTITY.value: 0.6,  # People/places are fairly important
            MemoryType.WORKFLOW.value: 0.6,  # Patterns are useful
            MemoryType.CONVERSATION.value: 0.4,  # Conversation excerpts less so
        }

        base_score = type_importance.get(memory_type, 0.5)

        # Adjust based on content length (longer = potentially more important)
        length_bonus = min(0.1, len(content) / 1000)

        return min(1.0, base_score + length_bonus)

    async def get_memory_stats(self, user_id: int) -> Dict[str, Any]:
        """Get memory statistics for a user.

        Args:
            user_id: The user's database ID

        Returns:
            Dictionary of memory statistics
        """
        total = await self.repository.count_user_memories(user_id)

        # Count by type
        type_counts = {}
        for memory_type in MemoryType:
            memories = await self.repository.get_user_memories(
                user_id=user_id,
                memory_type=memory_type.value,
                limit=1,
            )
            type_counts[memory_type.value] = len(memories)

        return {
            "total_memories": total,
            "by_type": type_counts,
        }
