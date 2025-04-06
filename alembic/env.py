import os
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool, engine_from_config, create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from dotenv import load_dotenv
import json

load_dotenv()

# this is the Alembic Config object
config = context.config

# Override sqlalchemy.url with environment variable
dsn = os.getenv("POSTGRES_DSN")
if not dsn:
    raise ValueError("POSTGRES_DSN environment variable is required")

# Remove asyncpg+postgresql:// if present and replace with postgresql://
# This is because Alembic works better with the sync driver for migrations
sync_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
sync_dsn = sync_dsn.replace("?ssl=require", "") # Remove ssl parameter from URL

# Configure Alembic with the basic URL
config.set_main_option("sqlalchemy.url", sync_dsn)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from raiden.db.models import Base
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a synchronous connection."""
    # Create engine with SSL requirements for Neon
    connectable = create_engine(
        sync_dsn,
        poolclass=pool.NullPool,
        connect_args={
            "sslmode": "require",
        }
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
