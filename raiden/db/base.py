# raiden/db/base.py
"""
Sets up the SQLAlchemy async engine, session management, and declarative base.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional  # <-- Added Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.exc import SQLAlchemyError

# Import settings from the core config module
from raiden.core.config import settings

logger = logging.getLogger(__name__)

# Global engine and session maker (initialized later)
# Use Optional typing and initialize to None
_async_engine: Optional[create_async_engine] = None
_async_session_local: Optional[async_sessionmaker[AsyncSession]] = None

class Base(DeclarativeBase):
    """Base class for SQLAlchemy declarative models."""
    pass

async def initialize_database():
    """
    Creates the async engine and session maker.
    Should be called during application startup.
    """
    global _async_engine, _async_session_local
    if _async_engine is None:
        # Log the DSN safely by masking the password part if present
        dsn_string_for_log = "DSN not set"
        if settings.postgres_dsn:
             try:
                  # Basic masking for typical DSN formats
                  parts = str(settings.postgres_dsn).split('@')
                  if len(parts) == 2 and ':' in parts[0]:
                       user_part = parts[0].split(':')[0]
                       dsn_string_for_log = f"{user_part}:******@{parts[1]}"
                  else:
                       dsn_string_for_log = str(settings.postgres_dsn) # Log as is if format is unusual
             except Exception:
                  dsn_string_for_log = "[Error masking DSN]"


        logger.info(f"Initializing PostgreSQL async engine for DSN: {dsn_string_for_log}")
        if not settings.postgres_dsn:
             raise ValueError("POSTGRES_DSN is not configured in settings.")

        try:
            _async_engine = create_async_engine(
                str(settings.postgres_dsn), # Pass the validated DSN string
                pool_pre_ping=True, # Checks connections before use, good for serverless/long idle
                pool_recycle=1800, # Recycle connections every 30 mins (adjust as needed for Neon/idle timeouts)
                # Consider pool size based on expected concurrency and Neon limits (adjust defaults if needed)
                pool_size=10, # Default: 5 + overflow
                max_overflow=5, # Default: 10
                echo=settings.log_level == "DEBUG", # Log SQL statements only in DEBUG mode
                # Use connect_args for driver-specific options if needed
                # connect_args={"server_settings": {"application_name": "raiden_agent"}} # Example: Set app name in PG logs
            )
            _async_session_local = async_sessionmaker(
                bind=_async_engine,
                class_=AsyncSession,
                expire_on_commit=False # Recommended for async and FastAPI dependencies
            )
            logger.info("PostgreSQL async engine and session maker initialized.")

            # Optional: Create tables defined in Base subclasses if they don't exist
            # WARNING: In production, use a proper migration tool like Alembic instead of create_all.
            # This is included for ease of getting started locally.
            logger.warning("Attempting to create database tables via create_all (for local dev only - use migrations in production!)")
            async with _async_engine.begin() as conn:
                logger.info("Running Base.metadata.create_all...")
                # await conn.run_sync(Base.metadata.drop_all) # Use for resetting during dev
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Base.metadata.create_all execution complete.")

        except SQLAlchemyError as e:
            logger.error(f"Failed to initialize PostgreSQL engine or create tables: {e}", exc_info=True)
            raise RuntimeError(f"Database initialization failed: {e}") from e
        except Exception as e: # Catch other potential errors like invalid DSN format
             logger.error(f"Unexpected error during database initialization: {e}", exc_info=True)
             raise RuntimeError(f"Unexpected database initialization error: {e}") from e
    else:
        logger.warning("Database already initialized. Skipping re-initialization.")


async def close_database():
    """
    Disposes of the async engine connection pool.
    Should be called during application shutdown.
    """
    global _async_engine, _async_session_local
    if (_async_engine):
        logger.info("Closing PostgreSQL async engine connection pool.")
        await _async_engine.dispose()
        _async_engine = None
        _async_session_local = None
        logger.info("PostgreSQL async engine closed.")
    else:
         logger.info("PostgreSQL engine was not initialized or already closed.")


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides an asynchronous database session for dependency injection or direct use.
    Handles session creation, commit/rollback, and closing within a context.
    """
    if _async_session_local is None:
        logger.error("Database not initialized. Cannot get session. Call initialize_database() first.")
        raise RuntimeError("Database session factory not available.")

    session: AsyncSession = _async_session_local()
    try:
        logger.debug("DB Session acquired.")
        yield session
        # Commit transaction if code in 'yield' block succeeded
        await session.commit()
        logger.debug("DB Session committed successfully.")
    except SQLAlchemyError as e:
        logger.error(f"Database transaction failed: {e}", exc_info=True)
        await session.rollback()
        logger.debug("DB Session rolled back due to SQLAlchemyError.")
        raise # Re-raise the exception after rollback
    except Exception as e:
         logger.error(f"Error during database session context: {e}", exc_info=True)
         await session.rollback()
         logger.debug("DB Session rolled back due to generic exception.")
         raise
    finally:
        # Always close the session when exiting the context
        await session.close()
        logger.debug("DB Session closed.")

# Function to get the engine directly if needed (e.g., for alembic migrations later)
def get_engine():
    if _async_engine is None:
         raise RuntimeError("Database engine not initialized.")
    return _async_engine