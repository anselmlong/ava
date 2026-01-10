"""Memory system - pgvector embeddings

Revision ID: 002
Revises: 001
Create Date: 2026-01-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create memory_embeddings table
    op.create_table(
        "memory_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        # Memory content
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        # Memory categorization
        sa.Column(
            "memory_type",
            sa.String(50),
            nullable=False,
            server_default="fact",
        ),
        sa.Column("entity_type", sa.String(50), nullable=True),
        # Context
        sa.Column("source_conversation_id", sa.Integer(), nullable=True),
        sa.Column(
            "source_message_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=True,
            server_default="{}",
        ),
        # Importance and retrieval
        sa.Column(
            "importance_score",
            sa.Float(),
            nullable=False,
            server_default="0.5",
        ),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_accessed", sa.DateTime(timezone=True), nullable=True),
        # Metadata
        sa.Column(
            "memory_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String(100)),
            nullable=True,
            server_default="{}",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Soft delete
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_conversation_id"], ["conversations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add the vector column for embeddings (768 dimensions for text-embedding-004)
    op.execute("ALTER TABLE memory_embeddings ADD COLUMN embedding vector(768)")

    # Create indexes
    op.create_index("idx_memory_user", "memory_embeddings", ["user_id"])
    op.create_index("idx_memory_type", "memory_embeddings", ["memory_type"])
    op.create_index(
        "idx_memory_importance",
        "memory_embeddings",
        [sa.text("importance_score DESC")],
    )

    # Create partial index for active (non-deleted) memories
    op.execute(
        """
        CREATE INDEX idx_memory_active ON memory_embeddings(user_id, deleted_at)
        WHERE deleted_at IS NULL
        """
    )

    # Create HNSW index for fast similarity search
    # m=16: number of bi-directional links (higher = better recall, more memory)
    # ef_construction=64: size of dynamic candidate list during construction
    op.execute(
        """
        CREATE INDEX idx_memory_embedding_hnsw ON memory_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # Create memory_consolidations table
    op.create_table(
        "memory_consolidations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "source_memory_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
        ),
        sa.Column("consolidated_memory_id", sa.Integer(), nullable=True),
        sa.Column("consolidation_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["consolidated_memory_id"], ["memory_embeddings.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_memory_consolidations_user",
        "memory_consolidations",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("memory_consolidations")
    op.drop_table("memory_embeddings")
    # Note: We don't drop the vector extension as it might be used elsewhere
