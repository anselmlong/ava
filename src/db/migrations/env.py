"""Alembic migration environment."""

import asyncio
import logging
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import models and settings
from src.db.models import Base
from src.config.settings import settings

# Alembic Config object
config = context.config

# Set the database URL from settings
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    logger = logging.getLogger("alembic.env")
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    except OSError as e:
        if e.errno == 101:  # Network is unreachable
            url_str = config.get_main_option("sqlalchemy.url")
            if url_str:
                url = make_url(url_str)
                logger.error(
                    "Network is unreachable connecting to PostgreSQL host=%s port=%s db=%s. "
                    "If you're using Supabase, the direct db.<project>.supabase.co endpoint may be IPv6-only; "
                    "use the Supabase pooler (IPv4) endpoint or enable IPv6 in Docker/host networking.",
                    url.host or "<unknown>",
                    url.port or "<unknown>",
                    url.database or "<unknown>",
                )
            else:
                logger.error(
                    "Network is unreachable connecting to PostgreSQL. "
                    "If you're using Supabase, the direct db.<project>.supabase.co endpoint may be IPv6-only; "
                    "use the Supabase pooler (IPv4) endpoint or enable IPv6 in Docker/host networking."
                )
        raise
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
