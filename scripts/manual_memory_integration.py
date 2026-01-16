#!/usr/bin/env python3
"""Manual integration test script for the Memory System.

Run this script to test the memory system with the real database and API.

Usage:
    # From project root:
    python scripts/manual_memory_integration.py

Requirements:
    - PostgreSQL with pgvector running (docker compose up -d postgres)
    - Valid GOOGLE_API_KEY in .env file
    - Database migrations applied (alembic upgrade head)
"""

import asyncio
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


async def test_embedding_service():
    """Test 1: Embedding Service."""
    print("\n" + "=" * 60)
    print("TEST 1: Embedding Service")
    print("=" * 60)

    from src.services.embedding import get_embedding_service

    try:
        service = get_embedding_service()
        print(f"Model: {service.model_name}")
        print(f"Dimension: {service.dimension}")

        # Test single embedding
        text = "The user lives in San Francisco and works as a software engineer."
        print(f"\nGenerating embedding for: '{text[:50]}...'")

        embedding = await service.embed_text(text)
        print(f"Embedding dimension: {len(embedding)}")
        print(f"First 5 values: {embedding[:5]}")

        # Test query embedding
        query = "Where does the user live?"
        print(f"\nGenerating query embedding for: '{query}'")

        query_embedding = await service.embed_query(query)
        print(f"Query embedding dimension: {len(query_embedding)}")

        print("\n[PASS] Embedding service working correctly!")
        return True

    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        return False


async def test_memory_repository():
    """Test 2: Memory Repository (Database Operations)."""
    print("\n" + "=" * 60)
    print("TEST 2: Memory Repository")
    print("=" * 60)

    from src.db.session import get_session
    from src.db.repositories.memory import MemoryRepository
    from src.db.repositories.user import UserRepository
    from src.db.models import MemoryType

    try:
        async with get_session() as session:
            user_repo = UserRepository(session)
            memory_repo = MemoryRepository(session)

            # Get or create test user
            user, created = await user_repo.get_or_create(
                telegram_id=11111111,
                username="phase2test",
                first_name="Phase2",
                auto_approve=True,
            )
            await session.commit()
            print(f"Test user: {user.full_name} (ID: {user.id}, new: {created})")

            # Create a test memory with embedding
            print("\nCreating test memory...")
            test_embedding = [0.1] * 768  # Mock embedding for testing

            memory = await memory_repo.create(
                user_id=user.id,
                content="User prefers Python programming language",
                embedding=test_embedding,
                memory_type=MemoryType.PREFERENCE.value,
                importance_score=0.8,
                tags=["programming", "preference"],
            )
            await session.commit()
            print(f"Created memory ID: {memory.id}")
            print(f"Content: {memory.content}")
            print(f"Type: {memory.memory_type}")
            print(f"Importance: {memory.importance_score}")

            # Retrieve memory
            print("\nRetrieving memory by ID...")
            retrieved = await memory_repo.get_by_id(memory.id)
            print(f"Retrieved: {retrieved.content}")

            # Get user memories
            print("\nListing user memories...")
            memories = await memory_repo.get_user_memories(user.id)
            print(f"Total memories for user: {len(memories)}")

            # Count memories
            count = await memory_repo.count_user_memories(user.id)
            print(f"Memory count: {count}")

            print("\n[PASS] Memory repository working correctly!")
            return True

    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_memory_service():
    """Test 3: Memory Service (High-Level Operations)."""
    print("\n" + "=" * 60)
    print("TEST 3: Memory Service")
    print("=" * 60)

    from src.db.session import get_session
    from src.services.memory import MemoryService
    from src.db.repositories.user import UserRepository
    from src.db.models import MemoryType

    try:
        async with get_session() as session:
            user_repo = UserRepository(session)

            # Get or create test user
            user, _ = await user_repo.get_or_create(
                telegram_id=22222222,
                username="memoryservicetest",
                first_name="MemService",
                auto_approve=True,
            )
            await session.commit()
            print(f"Test user: {user.full_name} (ID: {user.id})")

            # Create memory service
            memory_service = MemoryService(session)

            # Store memories
            print("\n--- Storing Memories ---")
            test_memories = [
                ("User lives in New York City", MemoryType.FACT.value),
                ("User prefers morning coffee at 7 AM", MemoryType.PREFERENCE.value),
                ("User's colleague is named Sarah", MemoryType.ENTITY.value),
                ("User usually exercises on weekends", MemoryType.WORKFLOW.value),
            ]

            stored_ids = []
            for content, mem_type in test_memories:
                memory = await memory_service.store_memory(
                    user_id=user.id,
                    content=content,
                    memory_type=mem_type,
                )
                stored_ids.append(memory.id)
                print(f"  Stored: '{content[:40]}...' (ID: {memory.id})")
            await session.commit()

            # Retrieve memories
            print("\n--- Retrieving Memories ---")
            queries = [
                "Where does the user live?",
                "What time does the user drink coffee?",
                "Who does the user work with?",
            ]

            for query in queries:
                print(f"\nQuery: '{query}'")
                memories = await memory_service.retrieve_relevant_memories(
                    user_id=user.id,
                    query=query,
                    limit=3,
                    include_scores=True,
                )
                for mem in memories[:2]:
                    score = mem.get("final_score", 0)
                    print(f"  -> {mem['content'][:50]}... (score: {score:.3f})")

            # Get conversation context
            print("\n--- Conversation Context ---")
            context = await memory_service.get_context_for_conversation(
                user_id=user.id,
                recent_messages=[
                    "I need to plan my morning",
                    "What should I do first?",
                ],
            )
            print(f"Context:\n{context}")

            # Get stats
            print("\n--- Memory Statistics ---")
            stats = await memory_service.get_memory_stats(user.id)
            print(f"Total memories: {stats['total_memories']}")

            print("\n[PASS] Memory service working correctly!")
            return True

    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_similarity_search():
    """Test 4: Semantic Similarity Search."""
    print("\n" + "=" * 60)
    print("TEST 4: Semantic Similarity Search")
    print("=" * 60)

    from src.db.session import get_session
    from src.services.memory import MemoryService
    from src.db.repositories.user import UserRepository
    from src.db.models import MemoryType

    try:
        async with get_session() as session:
            user_repo = UserRepository(session)

            # Get or create test user
            user, _ = await user_repo.get_or_create(
                telegram_id=33333333,
                username="similaritytest",
                first_name="Similarity",
                auto_approve=True,
            )
            await session.commit()

            memory_service = MemoryService(session)

            # Store diverse memories
            print("Storing diverse memories...")
            memories = [
                "User enjoys hiking and mountain climbing",
                "User's favorite programming language is Rust",
                "User has a pet cat named Whiskers",
                "User works at a tech startup in Silicon Valley",
                "User loves Italian food, especially pasta",
            ]

            for content in memories:
                await memory_service.store_memory(
                    user_id=user.id,
                    content=content,
                    memory_type=MemoryType.FACT.value,
                )
                print(f"  Stored: {content[:40]}...")
            await session.commit()

            # Test semantic search
            print("\n--- Semantic Search Results ---")
            test_queries = [
                ("outdoor activities", "Should match hiking"),
                ("coding preferences", "Should match Rust"),
                ("animals", "Should match cat"),
                ("career", "Should match tech startup"),
                ("food preferences", "Should match Italian food"),
            ]

            for query, expected in test_queries:
                print(f"\nQuery: '{query}' (expecting: {expected})")
                results = await memory_service.retrieve_relevant_memories(
                    user_id=user.id,
                    query=query,
                    limit=2,
                    include_scores=True,
                )
                for mem in results:
                    print(
                        f"  -> {mem['content'][:50]}... (score: {mem.get('final_score', 0):.3f})"
                    )

            print("\n[PASS] Similarity search working correctly!")
            return True

    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("PHASE 2: MEMORY SYSTEM TESTS")
    print(f"Started at: {datetime.now().isoformat()}")
    print("=" * 60)

    results = {}

    # Run tests
    results["Embedding Service"] = await test_embedding_service()
    results["Memory Repository"] = await test_memory_repository()
    results["Memory Service"] = await test_memory_service()
    results["Similarity Search"] = await test_similarity_search()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "PASS" if passed_test else "FAIL"
        print(f"  [{status}] {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\nAll tests passed! Phase 2 implementation is working.")
    else:
        print("\nSome tests failed. Check the output above for details.")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
