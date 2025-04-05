import logging
from typing import Optional, Dict, Any
from datetime import datetime

from raiden.core.models.internal_models import SessionState, Plan
from raiden.core.constants import (
    SessionStatus,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_FAILED,
    SESSION_STATUS_INITIALIZING,
)
from .storage.base_storage import BaseSessionStorage

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, cache_storage: BaseSessionStorage, persistent_storage: BaseSessionStorage):
        if not isinstance(cache_storage, BaseSessionStorage):
            raise TypeError("cache_storage must be an instance of BaseSessionStorage")
        if not isinstance(persistent_storage, BaseSessionStorage):
            raise TypeError("persistent_storage must be an instance of BaseSessionStorage")

        self.cache = cache_storage
        self.db = persistent_storage
        logger.info("SessionManager initialized with Cache and Persistent storage.")

    async def initialize_stores(self) -> None:
        logger.info("Initializing session storage backends...")
        await self.cache.initialize()
        await self.db.initialize()
        logger.info("Session storage backends initialized.")

    async def close_stores(self) -> None:
        logger.info("Closing session storage backends...")
        await self.cache.close()
        await self.db.close()
        logger.info("Session storage backends closed.")

    async def create_session(self, user_prompt: str, session_config: Optional[Dict[str, Any]] = None) -> SessionState:
        session = SessionState(
            user_prompt=user_prompt,
            status=SESSION_STATUS_INITIALIZING,
            session_config=session_config,
        )
        session_id = session.session_id
        logger.info(f"Creating new session {session_id} for prompt: '{user_prompt[:50]}...'")

        try:
            await self.cache.save_session(session)
            logger.debug(f"Session {session_id} saved to cache.")
            await self.db.save_session(session)
            logger.debug(f"Session {session_id} initial record saved to persistent storage.")
            return session
        except Exception as e:
            logger.error(f"Failed to create session {session_id} in storage: {e}", exc_info=True)
            raise RuntimeError(f"Session creation failed for {session_id}") from e

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        logger.debug(f"Attempting to retrieve session {session_id} from cache.")
        try:
            session = await self.cache.get_session(session_id)
            if session:
                logger.debug(f"Session {session_id} found in cache.")
                return session
            logger.debug(f"Session {session_id} not found in active cache.")
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id} from cache: {e}", exc_info=True)
            raise RuntimeError(f"Session retrieval failed for {session_id}") from e

    async def get_historical_session(self, session_id: str) -> Optional[SessionState]:
        logger.debug(f"Attempting to retrieve session {session_id} from persistent storage.")
        try:
            session = await self.db.get_session(session_id)
            if session:
                logger.debug(f"Session {session_id} found in persistent storage.")
                return session
            logger.debug(f"Session {session_id} not found in persistent storage.")
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id} from persistent storage: {e}", exc_info=True)
            raise RuntimeError(f"Historical session retrieval failed for {session_id}") from e

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> Optional[SessionState]:
        logger.debug(f"Attempting to update session {session_id} in cache with keys: {list(updates.keys())}.")
        updates["updated_at"] = datetime.utcnow()

        try:
            updated_session = await self.cache.update_session(session_id, updates)
            if not updated_session:
                logger.warning(f"Attempted to update session {session_id}, but it was not found in cache.")
                return None

            logger.debug(f"Session {session_id} updated successfully in cache. New status: {updated_session.status}")

            if updated_session.status in [SESSION_STATUS_COMPLETED, SESSION_STATUS_FAILED]:
                logger.info(f"Session {session_id} reached terminal state ({updated_session.status}). Persisting final state to DB.")
                try:
                    await self.db.save_session(updated_session)
                    logger.info(f"Final state of session {session_id} persisted to DB.")
                except Exception as db_e:
                    logger.error(f"Failed to persist terminal state for session {session_id} to DB: {db_e}", exc_info=True)

            return updated_session
        except (ValueError, RuntimeError) as e:
            logger.error(f"Update failed for session {session_id} in cache: {e}", exc_info=True)
            raise e
        except Exception as e:
            logger.error(f"Unexpected error updating session {session_id}: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected session update error for {session_id}") from e

    async def delete_session(self, session_id: str) -> bool:
        logger.info(f"Attempting to delete session {session_id} from cache.")
        try:
            deleted = await self.cache.delete_session(session_id)
            if deleted:
                logger.info(f"Session {session_id} deleted from cache.")
            else:
                logger.warning(f"Attempted to delete session {session_id}, but it was not found in cache.")
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete session {session_id} from cache: {e}", exc_info=True)
            raise RuntimeError(f"Session deletion failed for {session_id}") from e
