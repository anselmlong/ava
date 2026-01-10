from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from ..config import AppConfig
from .models import Base


_engine = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine(config: AppConfig):
    """Create (or reuse) a SQLAlchemy engine for the configured database."""

    global _engine
    if _engine is None:
        _engine = create_engine(config.database_url, future=True)
    return _engine


def get_session(config: AppConfig) -> Session:
    """Return a SQLAlchemy session bound to the configured database."""

    global _SessionLocal
    engine = get_engine(config)

    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False, expire_on_commit=False)

    return _SessionLocal()


def init_db(config: AppConfig) -> None:
    """Initialize the database schema and ensure PGVector is available.

    This will:
    - Ensure the `vector` extension exists (required for the Memory.embedding column)
    - Create all tables defined in the SQLAlchemy models
    """

    engine = get_engine(config)
    with engine.begin() as conn:
        # PGVector extension (no-op if it already exists)
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
