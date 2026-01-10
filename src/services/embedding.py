"""Embedding service for generating vector embeddings using Google text-embedding-004."""

from typing import List, Optional

import google.generativeai as genai

from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using Google's text-embedding-004 model.

    The text-embedding-004 model produces 768-dimensional vectors suitable for
    semantic similarity search with pgvector.
    """

    def __init__(self):
        """Initialize the embedding service."""
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required for embedding service")

        genai.configure(api_key=settings.google_api_key)
        self.model_name = f"models/{settings.embedding_model}"
        self.dimension = settings.embedding_dimension

    async def embed_text(self, text: str) -> List[float]:
        """Generate an embedding for a single text.

        Args:
            text: The text to embed

        Returns:
            A list of floats representing the embedding vector (768 dimensions)
        """
        try:
            # Use retrieval_document task type for content being indexed
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document",
            )
            return result["embedding"]
        except Exception as e:
            logger.error(
                "Error generating embedding", error=str(e), text_length=len(text)
            )
            raise

    async def embed_query(self, query: str) -> List[float]:
        """Generate an embedding optimized for search queries.

        Args:
            query: The search query to embed

        Returns:
            A list of floats representing the embedding vector (768 dimensions)
        """
        try:
            # Use retrieval_query task type for search queries
            result = genai.embed_content(
                model=self.model_name,
                content=query,
                task_type="retrieval_query",
            )
            return result["embedding"]
        except Exception as e:
            logger.error("Error generating query embedding", error=str(e), query=query)
            raise

    async def embed_batch(
        self,
        texts: List[str],
        task_type: str = "retrieval_document",
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            task_type: The task type for embeddings (retrieval_document or retrieval_query)

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        try:
            result = genai.embed_content(
                model=self.model_name,
                content=texts,
                task_type=task_type,
            )
            return result["embedding"]
        except Exception as e:
            logger.error(
                "Error generating batch embeddings",
                error=str(e),
                batch_size=len(texts),
            )
            raise


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get the embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
