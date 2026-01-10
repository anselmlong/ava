"""Tests for Phase 2: Memory System.

These tests cover:
1. EmbeddingService - generating embeddings
2. MemoryRepository - database operations with pgvector
3. MemoryService - high-level memory operations

Run with: pytest tests/test_memory_system.py -v
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.db.models import MemoryEmbedding, MemoryType, MemoryConsolidation
from src.db.repositories.memory import MemoryRepository
from src.services.embedding import EmbeddingService, get_embedding_service
from src.services.memory import MemoryService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_embedding():
    """Create a mock 768-dimensional embedding vector."""
    return [0.1] * 768


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    service = MagicMock(spec=EmbeddingService)
    service.embed_text = AsyncMock(return_value=[0.1] * 768)
    service.embed_query = AsyncMock(return_value=[0.1] * 768)
    service.embed_batch = AsyncMock(return_value=[[0.1] * 768, [0.2] * 768])
    return service


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service."""
    from src.services.llm.gemini import GeminiService

    service = MagicMock(spec=GeminiService)
    service.generate = AsyncMock(return_value="Generated response")
    return service


# =============================================================================
# EmbeddingService Tests
# =============================================================================


class TestEmbeddingService:
    """Tests for the EmbeddingService."""

    @pytest.mark.skipif(
        True,  # Skip by default as it requires API key
        reason="Requires GOOGLE_API_KEY environment variable",
    )
    async def test_embed_text_real_api(self):
        """Test embedding generation with real API (requires API key)."""
        service = get_embedding_service()
        embedding = await service.embed_text("Hello, world!")

        assert len(embedding) == 768
        assert all(isinstance(x, float) for x in embedding)

    async def test_embed_text_with_mock(self, mock_embedding_service):
        """Test embedding generation with mock service."""
        embedding = await mock_embedding_service.embed_text("Test text")

        assert len(embedding) == 768
        mock_embedding_service.embed_text.assert_called_once_with("Test text")

    async def test_embed_query_with_mock(self, mock_embedding_service):
        """Test query embedding generation with mock service."""
        embedding = await mock_embedding_service.embed_query("Search query")

        assert len(embedding) == 768
        mock_embedding_service.embed_query.assert_called_once_with("Search query")

    async def test_embed_batch_with_mock(self, mock_embedding_service):
        """Test batch embedding generation with mock service."""
        texts = ["Text 1", "Text 2"]
        embeddings = await mock_embedding_service.embed_batch(texts)

        assert len(embeddings) == 2
        assert len(embeddings[0]) == 768


# =============================================================================
# MemoryRepository Tests
# =============================================================================


class TestMemoryRepository:
    """Tests for the MemoryRepository.

    These tests require a running PostgreSQL database with pgvector extension.
    """

    @pytest.fixture
    async def repository(self, session):
        """Create a memory repository with test database session."""
        return MemoryRepository(session)

    @pytest.fixture
    async def test_user(self, session):
        """Create a test user."""
        from src.db.repositories.user import UserRepository

        user_repo = UserRepository(session)
        user, _ = await user_repo.get_or_create(
            telegram_id=12345678,
            username="testuser",
            first_name="Test",
            auto_approve=True,
        )
        await session.commit()
        return user

    async def test_create_memory(self, repository, test_user, mock_embedding):
        """Test creating a new memory with embedding."""
        memory = await repository.create(
            user_id=test_user.id,
            content="User lives in San Francisco",
            embedding=mock_embedding,
            memory_type=MemoryType.FACT.value,
            importance_score=0.7,
            tags=["location", "personal"],
        )

        assert memory.id is not None
        assert memory.user_id == test_user.id
        assert memory.content == "User lives in San Francisco"
        assert memory.memory_type == MemoryType.FACT.value
        assert memory.importance_score == 0.7
        assert "location" in memory.tags

    async def test_get_by_id(self, repository, test_user, mock_embedding):
        """Test retrieving memory by ID."""
        created = await repository.create(
            user_id=test_user.id,
            content="Test memory",
            embedding=mock_embedding,
        )

        retrieved = await repository.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.content == "Test memory"

    async def test_search_similar(self, repository, test_user, mock_embedding):
        """Test semantic similarity search."""
        # Create multiple memories
        await repository.create(
            user_id=test_user.id,
            content="User prefers morning workouts",
            embedding=[0.9] * 768,
            memory_type=MemoryType.PREFERENCE.value,
        )
        await repository.create(
            user_id=test_user.id,
            content="User likes coffee",
            embedding=[0.1] * 768,
            memory_type=MemoryType.PREFERENCE.value,
        )

        # Search with query embedding
        results = await repository.search_similar(
            user_id=test_user.id,
            query_embedding=[0.85] * 768,
            limit=5,
            similarity_threshold=0.5,
        )

        assert len(results) >= 1
        # Results should be tuples of (memory, similarity_score)
        memory, score = results[0]
        assert memory.content in ["User prefers morning workouts", "User likes coffee"]
        assert 0.0 <= score <= 1.0

    async def test_get_user_memories(self, repository, test_user, mock_embedding):
        """Test retrieving all memories for a user."""
        # Create several memories
        for i in range(3):
            await repository.create(
                user_id=test_user.id,
                content=f"Memory {i}",
                embedding=mock_embedding,
            )

        memories = await repository.get_user_memories(user_id=test_user.id)

        assert len(memories) >= 3

    async def test_soft_delete(self, repository, test_user, mock_embedding):
        """Test soft deleting a memory."""
        memory = await repository.create(
            user_id=test_user.id,
            content="Memory to delete",
            embedding=mock_embedding,
        )

        deleted = await repository.soft_delete(memory.id)

        assert deleted is not None
        assert deleted.deleted_at is not None
        assert deleted.is_deleted is True

        # Should not appear in normal queries
        memories = await repository.get_user_memories(user_id=test_user.id)
        deleted_memory_ids = [m.id for m in memories]
        assert memory.id not in deleted_memory_ids

    async def test_update_access(self, repository, test_user, mock_embedding):
        """Test updating memory access stats."""
        memory = await repository.create(
            user_id=test_user.id,
            content="Frequently accessed memory",
            embedding=mock_embedding,
        )
        initial_count = memory.access_count

        await repository.update_access(memory.id)

        # Refresh from database
        updated = await repository.get_by_id(memory.id)
        assert updated.access_count == initial_count + 1
        assert updated.last_accessed is not None


# =============================================================================
# MemoryService Tests
# =============================================================================


class TestMemoryService:
    """Tests for the high-level MemoryService."""

    @pytest.fixture
    async def memory_service(self, session, mock_embedding_service, mock_llm_service):
        """Create a MemoryService with mocked dependencies."""
        return MemoryService(
            session=session,
            embedding_service=mock_embedding_service,
            llm_service=mock_llm_service,
        )

    @pytest.fixture
    async def test_user(self, session):
        """Create a test user."""
        from src.db.repositories.user import UserRepository

        user_repo = UserRepository(session)
        user, _ = await user_repo.get_or_create(
            telegram_id=99999999,
            username="memoryuser",
            first_name="Memory",
            auto_approve=True,
        )
        await session.commit()
        return user

    async def test_store_memory(self, memory_service, test_user):
        """Test storing a new memory."""
        memory = await memory_service.store_memory(
            user_id=test_user.id,
            content="User's favorite color is blue",
            memory_type=MemoryType.PREFERENCE.value,
        )

        assert memory.id is not None
        assert memory.user_id == test_user.id
        assert "blue" in memory.content.lower()
        assert memory.memory_type == MemoryType.PREFERENCE.value

    async def test_retrieve_relevant_memories(self, memory_service, test_user):
        """Test retrieving relevant memories for a query."""
        # Store some memories first
        await memory_service.store_memory(
            user_id=test_user.id,
            content="User works as a software engineer",
            memory_type=MemoryType.FACT.value,
        )
        await memory_service.store_memory(
            user_id=test_user.id,
            content="User prefers Python programming",
            memory_type=MemoryType.PREFERENCE.value,
        )

        # Retrieve memories
        memories = await memory_service.retrieve_relevant_memories(
            user_id=test_user.id,
            query="What programming language does the user like?",
        )

        assert isinstance(memories, list)
        # Memories should have expected fields
        if memories:
            assert "content" in memories[0]
            assert "memory_type" in memories[0]

    async def test_get_context_for_conversation(self, memory_service, test_user):
        """Test getting context string for LLM."""
        # Store a memory
        await memory_service.store_memory(
            user_id=test_user.id,
            content="User's birthday is January 15",
            memory_type=MemoryType.FACT.value,
        )

        context = await memory_service.get_context_for_conversation(
            user_id=test_user.id,
            recent_messages=["When is my birthday?"],
        )

        # Context should be a formatted string
        assert isinstance(context, str)

    async def test_calculate_importance(self, memory_service):
        """Test importance score calculation."""
        # Preferences should have higher importance
        pref_score = await memory_service._calculate_importance(
            content="Short content",
            memory_type=MemoryType.PREFERENCE.value,
        )

        conv_score = await memory_service._calculate_importance(
            content="Short content",
            memory_type=MemoryType.CONVERSATION.value,
        )

        assert pref_score > conv_score
        assert 0.0 <= pref_score <= 1.0
        assert 0.0 <= conv_score <= 1.0

    async def test_get_memory_stats(self, memory_service, test_user):
        """Test getting memory statistics."""
        # Store a few memories
        await memory_service.store_memory(
            user_id=test_user.id,
            content="Fact 1",
            memory_type=MemoryType.FACT.value,
        )
        await memory_service.store_memory(
            user_id=test_user.id,
            content="Preference 1",
            memory_type=MemoryType.PREFERENCE.value,
        )

        stats = await memory_service.get_memory_stats(test_user.id)

        assert "total_memories" in stats
        assert stats["total_memories"] >= 2
        assert "by_type" in stats


# =============================================================================
# Integration Tests
# =============================================================================


class TestMemorySystemIntegration:
    """Integration tests for the complete memory system.

    These tests verify the full flow from storing to retrieving memories.
    """

    @pytest.fixture
    async def memory_service(self, session, mock_embedding_service, mock_llm_service):
        """Create a MemoryService for integration testing."""
        return MemoryService(
            session=session,
            embedding_service=mock_embedding_service,
            llm_service=mock_llm_service,
        )

    @pytest.fixture
    async def test_user(self, session):
        """Create a test user."""
        from src.db.repositories.user import UserRepository

        user_repo = UserRepository(session)
        user, _ = await user_repo.get_or_create(
            telegram_id=88888888,
            username="integrationuser",
            first_name="Integration",
            auto_approve=True,
        )
        await session.commit()
        return user

    async def test_full_memory_lifecycle(self, memory_service, test_user):
        """Test the complete lifecycle of a memory."""
        # 1. Store a memory
        memory = await memory_service.store_memory(
            user_id=test_user.id,
            content="User loves hiking in the mountains",
            memory_type=MemoryType.PREFERENCE.value,
            tags=["outdoor", "hobby"],
        )
        assert memory.id is not None

        # 2. Retrieve it
        memories = await memory_service.retrieve_relevant_memories(
            user_id=test_user.id,
            query="What outdoor activities does the user enjoy?",
        )
        assert len(memories) >= 1

        # 3. Get context for conversation
        context = await memory_service.get_context_for_conversation(
            user_id=test_user.id,
            recent_messages=["Let's plan a weekend trip"],
        )
        assert isinstance(context, str)

        # 4. Check stats
        stats = await memory_service.get_memory_stats(test_user.id)
        assert stats["total_memories"] >= 1

    async def test_memory_types_segregation(self, memory_service, test_user):
        """Test that different memory types are properly categorized."""
        # Store different types of memories
        await memory_service.store_memory(
            user_id=test_user.id,
            content="User's name is John",
            memory_type=MemoryType.FACT.value,
        )
        await memory_service.store_memory(
            user_id=test_user.id,
            content="User prefers dark mode",
            memory_type=MemoryType.PREFERENCE.value,
        )
        await memory_service.store_memory(
            user_id=test_user.id,
            content="John's friend Sarah",
            memory_type=MemoryType.ENTITY.value,
            entity_type="person",
        )

        # Verify stats reflect different types
        stats = await memory_service.get_memory_stats(test_user.id)
        assert stats["total_memories"] >= 3


# =============================================================================
# Manual Test Cases (for running without pytest)
# =============================================================================


async def manual_test_with_real_api():
    """Manual test that uses real API calls.

    Run this directly with:
        python -c "import asyncio; from tests.test_memory_system import manual_test_with_real_api; asyncio.run(manual_test_with_real_api())"
    """
    from src.db.session import get_session
    from src.services.memory import MemoryService
    from src.db.repositories.user import UserRepository

    print("=" * 60)
    print("Manual Memory System Test with Real API")
    print("=" * 60)

    async with get_session() as session:
        # Get or create test user
        user_repo = UserRepository(session)
        user, created = await user_repo.get_or_create(
            telegram_id=11111111,
            username="manualtest",
            first_name="Manual",
            auto_approve=True,
        )
        await session.commit()
        print(f"\nUser: {user.full_name} (ID: {user.id}, created: {created})")

        # Create memory service
        memory_service = MemoryService(session)

        # Test 1: Store memories
        print("\n--- Test 1: Storing Memories ---")
        memories_to_store = [
            ("I live in San Francisco", "fact"),
            ("I prefer morning meetings", "preference"),
            ("My friend Alice works at Google", "entity"),
            ("I usually check email at 9 AM", "workflow"),
        ]

        for content, mem_type in memories_to_store:
            memory = await memory_service.store_memory(
                user_id=user.id,
                content=content,
                memory_type=mem_type,
            )
            print(f"  Stored: '{content[:40]}...' (ID: {memory.id}, type: {mem_type})")
        await session.commit()

        # Test 2: Retrieve memories
        print("\n--- Test 2: Retrieving Memories ---")
        queries = [
            "Where does the user live?",
            "When does the user prefer to have meetings?",
            "Tell me about the user's friends",
        ]

        for query in queries:
            print(f"\n  Query: '{query}'")
            memories = await memory_service.retrieve_relevant_memories(
                user_id=user.id,
                query=query,
                include_scores=True,
            )
            for mem in memories[:3]:
                print(
                    f"    - {mem['content'][:50]}... (score: {mem.get('final_score', 'N/A'):.2f})"
                )

        # Test 3: Get conversation context
        print("\n--- Test 3: Conversation Context ---")
        context = await memory_service.get_context_for_conversation(
            user_id=user.id,
            recent_messages=[
                "What should I do today?",
                "Can you help me plan my morning?",
            ],
        )
        print(f"  Context:\n{context}")

        # Test 4: Memory stats
        print("\n--- Test 4: Memory Statistics ---")
        stats = await memory_service.get_memory_stats(user.id)
        print(f"  Total memories: {stats['total_memories']}")
        print(f"  By type: {stats['by_type']}")

        print("\n" + "=" * 60)
        print("Manual test completed!")
        print("=" * 60)


if __name__ == "__main__":
    import asyncio

    asyncio.run(manual_test_with_real_api())
