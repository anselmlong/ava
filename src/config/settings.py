"""Application settings using Pydantic."""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "ava"
    environment: str = Field(
        default="development", description="development, staging, production"
    )
    debug: bool = False
    log_level: str = "INFO"
    default_timezone: str = Field(
        default="Asia/Singapore",
        description="Default timezone for new users (IANA timezone name)",
    )

    # Telegram
    telegram_bot_token: str = Field(default="", description="Telegram Bot API token")
    telegram_admin_ids: str = Field(
        default="", description="Comma-separated list of admin Telegram user IDs"
    )

    @property
    def admin_ids(self) -> List[int]:
        """Parse admin IDs from comma-separated string."""
        if not self.telegram_admin_ids:
            return []
        return [
            int(id.strip()) for id in self.telegram_admin_ids.split(",") if id.strip()
        ]

    @property
    def db_components(self) -> dict:
        """Parse database URL into components for Mem0 configuration."""
        from urllib.parse import urlparse

        # Remove async driver prefix for parsing
        url = self.database_url.replace("postgresql+asyncpg://", "postgresql://")
        parsed = urlparse(url)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "user": parsed.username or "ava",
            "password": parsed.password or "",
            "dbname": parsed.path.lstrip("/") or "ava",
        }

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://ava:ava_dev_password@localhost:5432/ava",
        description="PostgreSQL connection URL",
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_pool_timeout: int = 30

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )

    # Google Gemini
    google_api_key: Optional[str] = Field(
        default=None, description="Google API key for Gemini"
    )
    gemini_model: str = "gemini-2.0-flash-exp"
    gemini_temperature: float = 0.7
    gemini_max_tokens: int = 2048

    # Embeddings (Google text-embedding-004)
    embedding_model: str = "text-embedding-004"
    embedding_dimension: int = 768  # text-embedding-004 produces 768-dim vectors

    # Agent
    langgraph_agent_enabled: bool = False

    # Memory System (Mem0)
    memory_read_enabled: bool = True
    memory_write_enabled: bool = True
    memory_retrieval_top_k: int = 5  # Number of memories to retrieve

    # Neo4j Graph Memory
    mem0_graph_enabled: bool = Field(
        default=True, description="Enable Neo4j graph memory for entity relationships"
    )
    mem0_neo4j_url: str = Field(
        default="bolt://localhost:7687", description="Neo4j Bolt connection URL"
    )
    mem0_neo4j_username: str = Field(default="neo4j", description="Neo4j username")
    mem0_neo4j_password: str = Field(default="", description="Neo4j password")

    # Rate limiting (per user)
    rate_limit_messages_per_minute: int = 30
    rate_limit_enabled: bool = True

    # Reminders
    reminder_poll_interval_seconds: int = 30
    reminder_dispatch_batch_size: int = 50

    # Security
    secret_key: str = Field(
        default="dev-secret-key-change-in-production-min-32-chars",
        description="Secret key for encryption (min 32 chars)",
    )

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Normalize DATABASE_URL for SQLAlchemy asyncio.

        SQLAlchemy's asyncio engine requires an async driver (asyncpg). It's
        common for Postgres URLs to be provided as `postgresql://...` or
        `postgres://...`, so we rewrite those to `postgresql+asyncpg://...`.
        """

        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://") :]

        if v.startswith("postgresql+psycopg2://"):
            return v.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)

        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)

        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Ensure secret key is long enough for production."""
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    def is_admin(self, telegram_id: int) -> bool:
        """Check if a Telegram user ID is an admin."""
        return telegram_id in self.admin_ids


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
