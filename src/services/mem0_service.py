"""Mem0 memory service for semantic long-term memory with graph relationships."""

from typing import Optional

from mem0 import Memory

from src.config.logging import get_logger
from src.config.settings import settings

logger = get_logger(__name__)


class Mem0Service:
    """Service for managing AI memory using Mem0 with optional Neo4j graph store."""

    _instance: Optional["Mem0Service"] = None

    def __init__(self):
        """Initialize Mem0 with configured providers."""
        db = settings.db_components

        config: dict = {
            "vector_store": {
                "provider": "pgvector",
                "config": {
                    "dbname": db["dbname"],
                    "host": db["host"],
                    "port": db["port"],
                    "user": db["user"],
                    "password": db["password"],
                    "collection_name": "mem0_memories",
                    "embedding_model_dims": settings.embedding_dimension,
                },
            },
            "llm": {
                "provider": "google",
                "config": {
                    "model": settings.gemini_model,
                    "api_key": settings.google_api_key,
                },
            },
            "embedder": {
                "provider": "google",
                "config": {
                    "model": settings.embedding_model,
                    "api_key": settings.google_api_key,
                },
            },
        }

        # Add graph store if enabled
        if settings.mem0_graph_enabled and settings.mem0_neo4j_password:
            config["graph_store"] = {
                "provider": "neo4j",
                "config": {
                    "url": settings.mem0_neo4j_url,
                    "username": settings.mem0_neo4j_username,
                    "password": settings.mem0_neo4j_password,
                },
            }
            logger.info("Mem0 initialized with Neo4j graph memory")
        else:
            logger.info("Mem0 initialized without graph memory")

        self.memory = Memory.from_config(config)

    @classmethod
    def get_instance(cls) -> "Mem0Service":
        """Get singleton instance of Mem0Service."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def store_conversation(self, user_id: int, messages: list[dict]) -> None:
        """Store conversation and auto-extract memories.

        Args:
            user_id: The user's database ID
            messages: List of message dicts with 'role' and 'content' keys
        """
        try:
            self.memory.add(messages, user_id=str(user_id))
            logger.debug("Stored conversation memories", user_id=user_id)
        except Exception as e:
            logger.warning("Failed to store memories", user_id=user_id, error=str(e))

    def get_context(self, user_id: int, query: str, limit: int = 5) -> str:
        """Retrieve relevant memories formatted as context string.

        Args:
            user_id: The user's database ID
            query: The query to search for relevant memories
            limit: Maximum number of memories to retrieve

        Returns:
            Formatted string of relevant memories, or empty string if none found
        """
        try:
            results = self.memory.search(query=query, user_id=str(user_id), limit=limit)

            if not results.get("results"):
                return ""

            lines = ["[Relevant memories from past conversations:]"]
            for entry in results["results"]:
                lines.append(f"- {entry['memory']}")

            return "\n".join(lines)
        except Exception as e:
            logger.warning("Failed to retrieve memories", user_id=user_id, error=str(e))
            return ""

    def get_all_memories(self, user_id: int) -> list:
        """Get all memories for a user.

        Args:
            user_id: The user's database ID

        Returns:
            List of memory objects
        """
        try:
            result = self.memory.get_all(user_id=str(user_id))
            return result.get("results", [])
        except Exception as e:
            logger.warning("Failed to get all memories", user_id=user_id, error=str(e))
            return []

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a specific memory.

        Args:
            memory_id: The ID of the memory to delete

        Returns:
            True if deletion was successful
        """
        try:
            self.memory.delete(memory_id=memory_id)
            return True
        except Exception as e:
            logger.warning("Failed to delete memory", memory_id=memory_id, error=str(e))
            return False

    def delete_all_user_memories(self, user_id: int) -> bool:
        """Delete all memories for a user.

        Args:
            user_id: The user's database ID

        Returns:
            True if deletion was successful
        """
        try:
            self.memory.delete_all(user_id=str(user_id))
            return True
        except Exception as e:
            logger.warning(
                "Failed to delete all memories", user_id=user_id, error=str(e)
            )
            return False


# Lazy-initialized singleton
_mem0_service: Optional[Mem0Service] = None


def get_mem0_service() -> Mem0Service:
    """Get the Mem0 service singleton instance."""
    global _mem0_service
    if _mem0_service is None:
        _mem0_service = Mem0Service()
    return _mem0_service
